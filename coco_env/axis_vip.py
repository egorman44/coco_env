import cocotb
from cocotb.triggers import RisingEdge
from cocotb.handle import SimHandleBase, NonHierarchyObject
from cocotb.binary import BinaryValue
from cocotb.utils import get_sim_time
import random
import math
import logging
from enum import Enum, auto
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Optional, List, Union, Any, Iterator, Type


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
        self.bytes_in_line = 8

    def print_packet(self):
        """Prints the packet data in a hex dump format."""
        if not self.data:
            print(f"Packet {self.name} is empty")
            return

        # Calculate max position for alignment logic
        max_pos = max(0, len(self.data) - 1)
        # Calculate width of the position field
        pos_width = len(str(max_pos))
        
        for i in range(0, len(self.data), self.bytes_in_line):
            chunk = self.data[i : i + self.bytes_in_line]
            hex_bytes = " ".join(f"{b:02x}" for b in chunk)
            print(f"{i:0{pos_width}d}: {hex_bytes}")

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
                 width: int, tvalid: Optional[SimHandleBase] = None, tlast: Optional[SimHandleBase] = None, 
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
        self.tkeep_type = tkeep_type

# ==============================================================================
# AxisDriver
# ==============================================================================

class AxisDriver:
    """
    AXI Stream Master Driver (Abstract Base Class).
    """
    def __init__(self, name: str, axis_if: AxisIf, pkt0_word0: int = 1, config: AxisConfig = AxisConfig()):
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.axis_if = axis_if
        self.width = axis_if.width
        self.pkt0_word0 = pkt0_word0
        self.config = config
        self.tvalid_delay = 0

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
        """
        Drives tuser signal.
        This method should be overridden by child classes if tuser handling is needed.
        """
        if self.axis_if.tuser is not None:
             raise NotImplementedError("tuser signal is present but drive_tuser is not overridden")

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

        # Handle Endianness/Ordering based on pkt0_word0
        ordered_data = list(data_chunk)

        # Assumes tdata provided as List of byte lanes.
        # If pkt0_word0=1 (default), byte 0 is LSB. List index 0 drives LSB. No reverse.
        # If pkt0_word0=0, byte 0 is MSB (?). Need to reverse so byte 0 drives MSB lane (highest index).
        # OR byte 0 drives LSB but the DUT expects MSB first?
        # Reverting to simple logic: If pkt0_word0=0, reverse the list.
        
        if self.pkt0_word0 == 0:
             ordered_data.reverse()

        # Drive proper interface (Assumes List/CHISEL_VEC structure)
        # If not iterable, this will fail, which is intended per "assume tdata comes as a list"
        for i, val in enumerate(ordered_data):
            self.axis_if.tdata[i].value = val

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
    AXI Stream Monitor (Abstract Base Class).
    """
    def __init__(self, name: str, axis_if: AxisIf, aport: list = None, pkt0_word0: int = 0):
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.axis_if = axis_if
        self.aport = aport if aport is not None else []
        self.width = axis_if.width
        self.pkt0_word0 = pkt0_word0        

        self.data = []
        self.user = []
        self.pkt_size = 0
        self.pkt_cntr = 0

    def mon_tuser(self) -> None:
        """
        Monitors tuser signal.
        This method should be overridden by child classes if tuser handling is needed.
        """
        if self.axis_if.tuser is not None:
            raise NotImplementedError("tuser signal is present but mon_tuser is not overridden")

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
                 tkeep_val = (int(self.axis_if.tkeep.value) << 1) - 1
        
        return tkeep_val

    def _handle_no_tdata(self):
        """Handle cases where tdata is missing.
        
        This method should be overridden by child classes if tdata is not present.
        """
        raise ValueError("tdata signal is not present and _handle_no_tdata is not overridden")

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
                # Assume List of Signals
                data_list = [h.value for h in self.axis_if.tdata]

                if self.pkt0_word0 == 0:
                    data_list.reverse()
                
                for i, val in enumerate(data_list):
                    tdata_int |= (val & 0xFF) << (i * 8)

                # Handle User
                self.mon_tuser()

                # Handle Keep / Masking
                if self.axis_if.tkeep is not None:
                     tkeep_val = self.mon_tkeep()
                else:
                     tkeep_val = self._handle_no_tkeep()

                # Calculate popcount for stats
                self.pkt_size += bin(tkeep_val).count('1')

                full_mask = 0
                for i in range(self.width):
                    if (tkeep_val >> i) & 1:
                        full_mask |= (0xFF << (i * 8))

                if self.pkt0_word0 == 0:
                    tkeep_mask = reverse_bits(full_mask, self.width * 8)
                else:
                    tkeep_mask = full_mask

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
