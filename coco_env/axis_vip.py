import cocotb
from cocotb.triggers import RisingEdge
from cocotb.handle import SimHandleBase, NonHierarchyObject
from cocotb.binary import BinaryValue
from cocotb.utils import get_sim_time
import random
import math
import logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Union, Any, Iterator

# ==============================================================================
# Enums and Configuration
# ==============================================================================

# Mock packet if not available in path or defined locally in axis_vip
class Packet:
    def __init__(self, name): 
        self.name = name
        self.data = []
        self.user = []
        self.pkt_size = 0
        self.delay = 0

    def words_to_bytes(self, word_list: List[int], total_bytes: int, width: int) -> None:
        """Converts a list of multi-byte words into a list of bytes.
        
        Args:
            word_list: List of integers representing words correctly packed
            total_bytes: Total number of valid bytes in the packet
            width: Width of the interface in bytes
        """
        self.pkt_size = total_bytes
        byte_list = []
        
        for word in word_list:
            for i in range(width):
                if len(byte_list) < total_bytes:
                    byte_list.append((word >> (i * 8)) & 0xFF)
                else:
                    break
        self.data = byte_list
         
class AxisPackingMode(Enum):
    """Defines how data is packed/unpacked in the signal."""
    PACKED = auto()      # Single wide signal
    UNPACKED = auto()    # List/Array of signals
    CHISEL_VEC = auto()  # Chisel Vec (List of signals)

class FlowControlMode(Enum):
    """Defines the flow control behavior for tvalid."""
    ALWAYS_ON = auto()
    ONE_VALID_ONE_NONVALID = auto()
    RANDOM = auto()

class AxisKeepType(Enum):
    """Defines the type of tkeep signal."""
    PACKED = auto()
    CHISEL_VEC = auto()
    FFS = auto()

@dataclass
class AxisConfig:
    """Configuration for AxisDriver and AxisResponder."""
    flow_ctrl_mode: FlowControlMode = FlowControlMode.ALWAYS_ON
    tvalid_low_limit: int = 0
    tvalid_high_limit: int = 1
    backpressure_min_delay: int = 1
    backpressure_max_delay: int = 5

def reverse_bits(value: int, width: int) -> int:
    """
    Reverses the bits of an integer within a specified width.
    Example: 0b0011 (width=4) -> 0b1100
    """
    result = 0
    for i in range(width):
        if (value >> i) & 1:
            result |= (1 << (width - 1 - i))
    return result

# ==============================================================================
# Interfaces
# ==============================================================================

class AxisIf:
    """Container for AXI Stream Interface signals."""

    def __init__(self, name: str, aclk: SimHandleBase, tdata: Union[SimHandleBase, List[SimHandleBase]], 
                 width: int, unpack: Optional[AxisPackingMode] = None, 
                 tvalid: Optional[SimHandleBase] = None, tlast: Optional[SimHandleBase] = None, 
                 tkeep: Optional[SimHandleBase] = None, tuser: Optional[SimHandleBase] = None, 
                 tready: Optional[SimHandleBase] = None, tkeep_type: AxisKeepType = AxisKeepType.CHISEL_VEC, uwidth: Optional[int] = None):
        self.name = name
        self.aclk = aclk
        self.tdata = tdata
        self.tvalid = tvalid
        self.tkeep = tkeep
        self.tlast = tlast
        self.tuser = tuser
        self.tready = tready
        self.width = width
        self.uwidth = uwidth
        self.unpack = unpack
        self.tkeep_type = tkeep_type

# ==============================================================================
# AxisDriver
# ==============================================================================

class AxisDriver:
    """
    AXI Stream Master Driver.
    """
    def __init__(self, name: str, axis_if: AxisIf, pkt0_word0: int = 1, config: AxisConfig = AxisConfig()):
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.axis_if = axis_if
        self.width = axis_if.width
        self.pkt0_word0 = pkt0_word0
        self.config = config
        
        # Auto-detect unpack mode if not provided
        if self.axis_if.unpack is None:
            self.unpack = self._detect_unpack_mode(self.axis_if.tdata)
            self.log.info(f"Auto-detected unpacking mode: {self.unpack.name}")
        else:
            self.unpack = self.axis_if.unpack

        self.tvalid_delay = 0

    # TODO: 
    def _detect_unpack_mode(self, tdata_handle: Any) -> AxisPackingMode:
        """
        Auto-detects whether tdata is unpacked (list-like) or packed (single signal).
        """
        return AxisPackingMode.CHISEL_VEC

    def _get_tvalid_value(self, tnx_completed: bool) -> int:
        """Determines the next value for tvalid based on flow control."""
        if self.config.flow_ctrl_mode == FlowControlMode.ALWAYS_ON:
            return 1
            
        elif self.config.flow_ctrl_mode == FlowControlMode.ONE_VALID_ONE_NONVALID:
            return 1 if not tnx_completed else 0
            
        elif self.config.flow_ctrl_mode == FlowControlMode.RANDOM:
            if tnx_completed:
                if self.tvalid_delay > 0:
                    self.tvalid_delay -= 1
                    return 0
                else:
                    self.tvalid_delay = random.randint(1, self.config.tvalid_low_limit)
                    return 0
            elif self.axis_if.tvalid.value == 0:
                if self.tvalid_delay > 0:
                    self.tvalid_delay -= 1
                    return 0
                else:
                    self.tvalid_delay = random.randint(1, self.config.tvalid_high_limit)
                    return 1
            return int(self.axis_if.tvalid.value)
            
        return 1

    def drive_tvalid(self, tnx_completed: bool) -> None:
        if self.axis_if.tvalid is not None:
            self.axis_if.tvalid.value = self._get_tvalid_value(tnx_completed)

    def drive_tlast(self, last_word: bool) -> None:
        if self.axis_if.tlast is not None:
            self.axis_if.tlast.value = 1 if last_word else 0

    def drive_tuser(self, pkt: Packet, last_word: bool) -> None:
        if self.axis_if.tuser is not None and pkt.user:
            self.axis_if.tuser.value = pkt.user[0]

    def drive_tkeep(self, pkt: Packet, last_word: bool) -> None:
        if self.axis_if.tkeep is not None:
            if last_word and pkt.pkt_size % self.width != 0:
                tkeep_msb_pos = pkt.pkt_size % self.width
            else:
                tkeep_msb_pos = self.width

            if self.axis_if.tkeep_type == AxisKeepType.FFS:
                tkeep = 1 << (tkeep_msb_pos - 1)
            else: # AxisKeepType.PACKED
                tkeep = (1 << tkeep_msb_pos) - 1

            if self.pkt0_word0 == 0:
                tkeep = reverse_bits(tkeep, self.width)
            
            self.axis_if.tkeep.value = tkeep

    def drive_tdata(self, pkt: Packet, last_word: bool, word_num: int) -> None:
        # Extract data slice
        start_idx = self.width * word_num
        if last_word:
            data_chunk = pkt.data[start_idx:]
        else:
            data_chunk = pkt.data[start_idx : start_idx + self.width]

        # Padding
        if len(data_chunk) < self.width:
             data_chunk.extend([0] * (self.width - len(data_chunk)))

        # Handle Endianness/Ordering based on pkt0_word0 and Packing Mode
        # pkt0_word0 = 1: byte 0 is LSB/First element
        # pkt0_word0 = 0: byte 0 is MSB/Last element
        
        ordered_data = list(data_chunk)

        needs_reverse = False
        if self.unpack == AxisPackingMode.UNPACKED:
             # For unpacked, list usually matches index. 
             # If pkt0_word0=1, index 0 is data[0]. If driver logic requires reversal:
             if self.pkt0_word0 == 1:
                 needs_reverse = True # Legacy behavior preserved: unpacked + pkt0_word0=1 => reverse
        
        elif self.unpack == AxisPackingMode.CHISEL_VEC:
             if self.pkt0_word0 == 0:
                 needs_reverse = True
        
        elif self.unpack == AxisPackingMode.PACKED:
             if self.pkt0_word0 == 0:
                 needs_reverse = True

        if needs_reverse:
            ordered_data.reverse()

        # Drive proper interface
        if self.unpack == AxisPackingMode.UNPACKED:
            self.axis_if.tdata.value = ordered_data
        
        elif self.unpack == AxisPackingMode.CHISEL_VEC:
            for i, val in enumerate(ordered_data):
                self.axis_if.tdata[i].value = val
                
        elif self.unpack == AxisPackingMode.PACKED:
            # Construct integer from bytes
            data_int = 0
            for i, byte_val in enumerate(ordered_data):
                data_int |= (byte_val & 0xFF) << (i * 8)
            self.axis_if.tdata.value = data_int

    def check_transaction_completion(self) -> bool:
        if self.axis_if.tready is None:
            return bool(self.axis_if.tvalid.value) if self.axis_if.tvalid else True
        else:
            return bool(self.axis_if.tvalid.value and self.axis_if.tready.value)

    async def send_pkt(self, pkt: Packet) -> None:
        self.log.info(f"Sending packet: {pkt.name}, size={pkt.pkt_size}")
        tnx_completed = False
        
        # Initial delay
        for _ in range(pkt.delay):
            await RisingEdge(self.axis_if.aclk)

        self.axis_if.tvalid.value = 1
        
        word_num = 0
        pkt_len_in_words = math.ceil(pkt.pkt_size / self.width)
        if pkt_len_in_words == 0:
             # Edge case: empty packet (if possible)
             pkt_len_in_words = 1 

        while word_num < pkt_len_in_words:
            last_word = (word_num == pkt_len_in_words - 1)
            
            self.drive_tlast(last_word)
            self.drive_tuser(pkt, last_word)
            self.drive_tkeep(pkt, last_word)
            self.drive_tdata(pkt, last_word, word_num)
            self.drive_tvalid(tnx_completed)
            
            await RisingEdge(self.axis_if.aclk)
            tnx_completed = self.check_transaction_completion()
            
            if tnx_completed:
                word_num += 1

        # Clean up
        if self.axis_if.tvalid is not None:
            self.axis_if.tvalid.value = 0
        if self.axis_if.tlast is not None:
            self.axis_if.tlast.value = 0
        
        self.log.debug(f"Finished sending packet: {pkt.name}")

# ==============================================================================
# AxisMonitor
# ==============================================================================

class AxisMonitor:
    """
    AXI Stream Monitor.
    """
    def __init__(self, name: str, axis_if: AxisIf, aport: list = None, pkt0_word0: int = 0):
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.axis_if = axis_if
        self.aport = aport if aport is not None else []
        self.width = axis_if.width
        self.pkt0_word0 = pkt0_word0        

        # Auto-detect unpack mode if not provided in interface
        if self.axis_if.unpack is None:
            # We can't reuse private method easily without inheritance or utility, but duplicating precise logic is fine here
            # or just creating utility class. For now, inline logic is fine.
            if isinstance(self.axis_if.tdata, (list, tuple)):
                 self.unpack = AxisPackingMode.UNPACKED
            elif hasattr(self.axis_if.tdata, '__iter__') and not hasattr(self.axis_if.tdata, 'value'):
                 self.unpack = AxisPackingMode.CHISEL_VEC
            else:
                 self.unpack = AxisPackingMode.PACKED
            self.log.info(f"Monitor Auto-detected unpacking mode: {self.unpack.name}")
        else:
            self.unpack = self.axis_if.unpack

        self.data = []
        self.user = []
        self.pkt_size = 0
        self.pkt_cntr = 0

    def mon_tuser(self) -> None:
        if self.axis_if.tuser is not None and self.axis_if.tlast is not None:
            if self.axis_if.tlast.value == 1:
                self.user.append(self.axis_if.tuser.value)

    def mon_tkeep(self) -> int:
        """
        Calculates the validity mask for the current word.
        Returns a bitmask where 1 indicates valid byte.
        """
        tkeep_val = 0
        
        if self.axis_if.tkeep_type == AxisKeepType.PACKED:
            tkeep_val = int(self.axis_if.tkeep.value)
        
        elif self.axis_if.tkeep_type == AxisKeepType.CHISEL_VEC:
            for i, signal in enumerate(self.axis_if.tkeep):
                if bool(signal.value):
                    tkeep_val |= (1 << i)
        
        elif self.axis_if.tkeep_type == AxisKeepType.FFS:
            if self.axis_if.tkeep.value == 0:
                 tkeep_val = 0
            else:
                 # FFS usually implies 1-hot or similar? 
                 # Legacy code: (value << 1) - 1. Example: 4 -> 8-1=7 (0b111)
                 tkeep_val = (int(self.axis_if.tkeep.value) << 1) - 1
        
        # Now we have the raw tkeep mask.
        # Calculate popcount for stats
        self.pkt_size += bin(tkeep_val).count('1')
        
        full_mask = 0
        for i in range(self.width):
            if (tkeep_val >> i) & 1:
                full_mask |= (0xFF << (i * 8))
        
        reversed_mask = reverse_bits(full_mask, self.width * 8)
        return reversed_mask

    async def mon_if(self) -> None:
        self.log.info("Starting AxisMonitor")
        while True:
            await RisingEdge(self.axis_if.aclk)
            
            if self.axis_if.tready is None:
                tnx_completed = bool(self.axis_if.tvalid.value)
            else:
                tnx_completed = bool(self.axis_if.tvalid.value and self.axis_if.tready.value)
            
            if tnx_completed:
                tdata_int = 0
                
                # capture raw data into integer
                if self.unpack == AxisPackingMode.UNPACKED:
                    # Legacy: loop byte_range, shift
                    # if pkt0_word0=1: ranges(width) (0..W-1)
                    # else: ranges(width)[::-1] (W-1..0)
                    # shift = index * 8
                    
                    # Essentially:
                    # if pkt0_word0=1: data[0] is Byte0 (LSB)
                    # if pkt0_word0=0: data[0] is ByteN (MSB?)
                    
                    data_list = [h.value for h in self.axis_if.tdata]
                    if self.pkt0_word0 == 0:
                        data_list.reverse()
                    
                    for i, val in enumerate(data_list):
                        tdata_int |= (val & 0xFF) << (i * 8)

                elif self.unpack == AxisPackingMode.CHISEL_VEC:
                    for i in range(self.width):
                        val = self.axis_if.tdata[i].value
                        tdata_int |= (val & 0xFF) << (i * 8)
                        
                elif self.unpack == AxisPackingMode.PACKED:
                    tdata_int = int(self.axis_if.tdata.value)
                    
                    # Legacy packed reversal logic:
                    # if pkt0_word0 == 0: reverse BYTES
                    if self.pkt0_word0 == 0 and self.width > 1:
                        # Reverse bytes
                        # We can use the helper function or bytes conversion
                        # bytes conversion is often faster/cleaner
                        try:
                            # Width in bytes
                            val_bytes = tdata_int.to_bytes(self.width, 'little')
                            # The legacy reverse loop effectively swaps endianness
                            tdata_int = int.from_bytes(val_bytes, 'big')
                            # Wait, legacy: for byte_indx ... tdata_rev |= ...
                            # Yes, effectively byte reversal
                        except OverflowError:
                            self.log.error("Data width mismatch during byte reversal")

                # Handle User
                self.mon_tuser()

                # Handle Keep / Masking
                if self.axis_if.tkeep is not None:
                     tkeep_mask = self.mon_tkeep()
                else:
                     tkeep_mask = self._handle_no_tkeep()

                self.data.append(tdata_int & tkeep_mask)

                # Check Last
                is_last = False
                if self.axis_if.tlast is not None:
                     if self.axis_if.tlast.value == 1:
                         is_last = True
                else: 
                     is_last = self._handle_no_tlast()
                
                if is_last:
                    self.write_aport()

    def _handle_no_tlast(self) -> bool:
        """Handle cases where tlast is missing.
        
        This method should be overridden by child classes if tlast is not present.
        """
        raise ValueError("tlast signal is not present and _handle_no_tlast is not overridden")

    def _handle_no_tkeep(self) -> int:
        """Handle cases where tkeep is missing.
        
        This method should be overridden by child classes if tkeep is not present.
        """
        raise ValueError("tkeep signal is not present and _handle_no_tkeep is not overridden")

    def write_aport(self) -> None:
        pkt_mon = Packet(f"{self.name}-{self.pkt_cntr}")
        pkt_mon.words_to_bytes(self.data, self.pkt_size, self.width)
        
        # self.log.info(f"Monitor captured packet: {pkt_mon.name}") # Verbose
        
        # Reset state
        self.data = []
        self.user = []
        self.pkt_size = 0
        
        self.aport.append(pkt_mon)
        self.pkt_cntr += 1

# ==============================================================================
# AxisResponder
# ==============================================================================

class AxisResponder:
    """
    AXI Stream Slave Responder (handles TREADY).
    """
    def __init__(self, name: str, axis_if: AxisIf, config: AxisConfig = AxisConfig()):
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.axis_if = axis_if
        self.config = config

    async def tready_ctrl(self) -> None:
        """Controls TREADY based on configured mode."""
        self.log.info("Starting AxisResponder")
        
        # If tready doesn't exist, nothing to do
        if self.axis_if.tready is None:
            return

        while True:
            if self.config.flow_ctrl_mode == FlowControlMode.ALWAYS_ON:
                self.axis_if.tready.value = 1
                await RisingEdge(self.axis_if.aclk)
                
            elif self.config.flow_ctrl_mode == FlowControlMode.RANDOM:
                # Example Logic: Backpressure logic from legacy "BACKPRESSURE_*"
                # We can implement a more generic random backpressure
                
                # Active phase
                self.axis_if.tready.value = 1
                active_cycles = random.randint(1, 10) 
                for _ in range(active_cycles):
                    await RisingEdge(self.axis_if.aclk)
                
                # Backpressure phase
                self.axis_if.tready.value = 0
                wait_cycles = random.randint(self.config.backpressure_min_delay, self.config.backpressure_max_delay)
                for _ in range(wait_cycles):
                    await RisingEdge(self.axis_if.aclk)

            else:
                 # Default Safe
                 self.axis_if.tready.value = 1
                 await RisingEdge(self.axis_if.aclk)
