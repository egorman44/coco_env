import cocotb
from cocotb.triggers import RisingEdge
import random
import math
import logging
from enum import Enum, auto
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Optional, List, Union, Any, Iterator, Type

from .rv_base import (
    Packet, FlowControlMode, DriverConfig, ResponderConfig,
    ReadyValidDriverBase, ReadyValidMonitorBase, ReadyValidResponderBase
)


# ==============================================================================
# AXIS-specific Enums and Configuration
# ==============================================================================

class AxisKeepType(Enum):
    """Defines the type of tkeep signal."""
    PACKED = auto()
    CHISEL_VEC = auto()
    FFS = auto()


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

@dataclass
class AxisIf:
    """Container for AXI Stream Interface signals."""
    name: str
    aclk: object                                        # clock handle
    tdata: object                                       # data signal or list of byte signals
    width: int                                          # interface width in bytes
    tvalid: object = None                               # valid signal handle
    tlast: object = None                                # last signal handle
    tkeep: object = None                                # keep signal handle
    tuser: object = None                                # user signal handle
    tready: object = None                               # ready signal handle
    tkeep_type: AxisKeepType = AxisKeepType.CHISEL_VEC  # keep encoding type


# ==============================================================================
# AxisDriver
# ==============================================================================

class AxisDriver(ReadyValidDriverBase):
    """
    AXI Stream Master Driver.

    Inherits ready-valid handshake and flow-control from ReadyValidDriverBase.
    Implements AXIS-specific tdata/tkeep/tuser/tlast driving.
    """

    def __init__(self, name: str, axis_if: AxisIf, pkt0_word0: int = 1, config: DriverConfig = DriverConfig()):
        super().__init__(
            name=name,
            clk=axis_if.aclk,
            valid=axis_if.tvalid,
            ready=axis_if.tready,
            config=config,
        )
        self.axis_if = axis_if
        self.width = axis_if.width
        self.pkt0_word0 = pkt0_word0

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------

    def get_num_words(self, pkt: Packet) -> int:
        return math.ceil(pkt.pkt_size / self.width)

    def drive_interface(self, pkt: Packet, last_word: bool, word_num: int) -> None:
        if self.axis_if.tlast is not None:
            self.axis_if.tlast.value = 1 if last_word else 0
        self.drive_tuser(pkt, last_word)
        self.drive_tkeep(pkt, last_word)
        self.drive_tdata(pkt, last_word, word_num)

    def drive_idle(self) -> None:
        if self.axis_if.tvalid is not None:
            self.axis_if.tvalid.value = 0
        if self.axis_if.tlast is not None:
            self.axis_if.tlast.value = 0

    # ------------------------------------------------------------------
    # AXIS-specific signal driving
    # ------------------------------------------------------------------

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

        if self.pkt0_word0 == 0:
             ordered_data.reverse()

        for i, val in enumerate(ordered_data):
            self.axis_if.tdata[i].value = val


# ==============================================================================
# AxisMonitor
# ==============================================================================

class AxisMonitor(ReadyValidMonitorBase):
    """
    AXI Stream Monitor.

    Inherits handshake detection and packet assembly from ReadyValidMonitorBase.
    Implements AXIS-specific tdata/tkeep/tuser/tlast sampling.
    """

    def __init__(self, name: str, axis_if: AxisIf, aport: list = None, pkt0_word0: int = 0, verbose: bool = False):
        super().__init__(
            name=name,
            clk=axis_if.aclk,
            valid=axis_if.tvalid,
            ready=axis_if.tready,
            aport=aport,
            verbose=verbose,
        )
        self.axis_if = axis_if
        self.width = axis_if.width
        self.pkt0_word0 = pkt0_word0

        # Keep the user accumulation list
        self.user = []

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------

    def sample_data(self) -> tuple:
        tdata_int = 0

        # Capture raw data into integer (assume List of Signals)
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

        # Calculate valid bytes (popcount)
        valid_bytes = bin(tkeep_val).count('1')

        # Build full mask
        full_mask = 0
        for i in range(self.width):
            if (tkeep_val >> i) & 1:
                full_mask |= (0xFF << (i * 8))

        if self.pkt0_word0 == 0:
            tkeep_mask = reverse_bits(full_mask, self.width * 8)
        else:
            tkeep_mask = full_mask

        return (tdata_int & tkeep_mask, valid_bytes)

    def is_last(self) -> bool:
        if self.axis_if.tlast is not None:
            return self.axis_if.tlast.value == 1
        else:
            return self._handle_no_tlast()

    def build_packet(self, pkt: Packet) -> None:
        pkt.words_to_bytes(self.raw_data, self.pkt_size, self.width)

    # ------------------------------------------------------------------
    # AXIS-specific helpers
    # ------------------------------------------------------------------

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
        """Handle cases where tdata is missing."""
        raise ValueError("tdata signal is not present and _handle_no_tdata is not overridden")

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


# ==============================================================================
# AxisResponder
# ==============================================================================

class AxisResponder(ReadyValidResponderBase):
    """
    AXI Stream Slave Responder (handles TREADY).
    """

    def __init__(self, name: str, axis_if: AxisIf, config: ResponderConfig = ResponderConfig()):
        super().__init__(
            name=name,
            clk=axis_if.aclk,
            ready=axis_if.tready,
            config=config,
        )
        self.axis_if = axis_if

    async def tready_ctrl(self) -> None:
        """Controls TREADY. Delegates to base ready_ctrl()."""
        await self.ready_ctrl()
