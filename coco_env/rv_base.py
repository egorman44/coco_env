import cocotb
from cocotb.triggers import RisingEdge
from cocotb.handle import SimHandleBase
import random
import math
import logging
from abc import ABC, abstractmethod
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, List


# ==============================================================================
# Mock Packet
# ==============================================================================

from .packet import Packet


# ==============================================================================
# Enums and Configuration
# ==============================================================================

class FlowControlMode(Enum):
    """Defines the flow control behavior for valid signal."""
    ALWAYS_ON = auto()
    ONE_VALID_ONE_NONVALID = auto()
    RANDOM = auto()


@dataclass
class ReadyValidConfig:
    """Configuration for ready-valid driver and responder."""
    flow_ctrl_mode: FlowControlMode = FlowControlMode.ALWAYS_ON
    tvalid_low_limit: int = 0
    tvalid_high_limit: int = 1
    backpressure_min_delay: int = 1
    backpressure_max_delay: int = 5


# ==============================================================================
# ReadyValidDriverBase
# ==============================================================================

class ReadyValidDriverBase(ABC):
    """
    Protocol-agnostic ready-valid driver (Abstract Base Class).

    Handles the valid-signal flow control and handshake logic.
    Subclasses must implement protocol-specific data driving.
    """

    def __init__(self, name: str, clk: SimHandleBase,
                 valid: Optional[SimHandleBase] = None,
                 ready: Optional[SimHandleBase] = None,
                 config: ReadyValidConfig = ReadyValidConfig()):
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.clk = clk
        self.valid = valid
        self.ready = ready
        self.config = config
        self.tvalid_delay = 0

    # ------------------------------------------------------------------
    # Valid-signal flow control
    # ------------------------------------------------------------------

    def _get_valid_value(self, tnx_completed: bool) -> int:
        """Determines the next value for valid based on flow control mode."""
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
            elif self.valid.value == 0:
                if self.tvalid_delay > 0:
                    self.tvalid_delay -= 1
                    return 0
                else:
                    self.tvalid_delay = random.randint(1, self.config.tvalid_high_limit)
                    return 1
            return int(self.valid.value)

        return 1

    def drive_valid(self, tnx_completed: bool) -> None:
        """Drive the valid signal based on flow control."""
        if self.valid is not None:
            self.valid.value = self._get_valid_value(tnx_completed)

    # ------------------------------------------------------------------
    # Handshake
    # ------------------------------------------------------------------
    
    def check_transaction_completion(self) -> bool:
        """Check if a transaction completed (valid & ready handshake)."""
        if self.ready is None:
            return bool(self.valid.value) if self.valid else True
        else:
            return bool(self.valid.value and self.ready.value)

    # ------------------------------------------------------------------
    # Main send loop
    # ------------------------------------------------------------------

    async def send_pkt(self, pkt: Packet) -> None:
        """Send a packet over the ready-valid interface.

        Iterates over words, calling abstract hooks for protocol-specific
        signal driving.
        """
        self.log.info(f"Sending packet: {pkt.name}, size={pkt.pkt_size}")
        tnx_completed = False

        # Initial delay
        for _ in range(pkt.delay):
            await RisingEdge(self.clk)

        if self.valid is not None:
            self.valid.value = 1

        word_num = 0
        num_words = self.get_num_words(pkt)
        if num_words == 0:
            num_words = 1  # Edge case: empty packet

        while word_num < num_words:
            last_word = (word_num == num_words - 1)

            self.drive_interface(pkt, last_word, word_num)
            self.drive_valid(tnx_completed)

            await RisingEdge(self.clk)
            tnx_completed = self.check_transaction_completion()

            if tnx_completed:
                word_num += 1

        # Clean up
        self.drive_idle()
        self.log.debug(f"Finished sending packet: {pkt.name}")

    # ------------------------------------------------------------------
    # Abstract / virtual methods for subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def get_num_words(self, pkt: Packet) -> int:
        """Return the number of beats (words) needed for this packet."""
        ...

    @abstractmethod
    def drive_interface(self, pkt: Packet, last_word: bool, word_num: int) -> None:
        """Drive all protocol-specific signals for one beat.

        This includes data, last, user, keep, etc. — whatever the
        protocol requires.  Called once per beat in the send loop.
        """
        ...

    @abstractmethod
    def drive_idle(self) -> None:
        """Clean up / idle all driven signals after packet completes."""
        ...


# ==============================================================================
# ReadyValidMonitorBase
# ==============================================================================

class ReadyValidMonitorBase(ABC):
    """
    Protocol-agnostic ready-valid monitor (Abstract Base Class).

    Handles the handshake detection and packet assembly loop.
    Subclasses must implement protocol-specific data sampling.
    """

    def __init__(self, name: str, clk: SimHandleBase,
                 valid: Optional[SimHandleBase] = None,
                 ready: Optional[SimHandleBase] = None,
                 aport: list = None, verbose: bool = False):
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.clk = clk
        self.valid = valid
        self.ready = ready
        self.aport = aport if aport is not None else []
        self.verbose = verbose

        # Per-packet accumulation state
        self.raw_data = []
        self.pkt_size = 0
        self.pkt_cntr = 0

    # ------------------------------------------------------------------
    # Main monitor loop
    # ------------------------------------------------------------------

    async def mon_if(self) -> None:
        """Forever-loop: await rising edge, check handshake, sample data."""
        self.log.info(f"Starting {self.name} monitor")
        while True:
            await RisingEdge(self.clk)

            if self.ready is None:
                tnx_completed = bool(self.valid.value)
            else:
                tnx_completed = bool(self.valid.value and self.ready.value)

            if tnx_completed:
                # Protocol-specific data sampling
                data_word, valid_bytes = self.sample_data()
                self.raw_data.append(data_word)
                self.pkt_size += valid_bytes

                if self.is_last():
                    self.write_aport()

    # ------------------------------------------------------------------
    # Packet assembly
    # ------------------------------------------------------------------

    def write_aport(self) -> None:
        """Build a Packet from accumulated data, append to aport, reset state."""
        pkt_mon = Packet(f"{self.name}-{self.pkt_cntr}")
        self.build_packet(pkt_mon)
        if self.verbose:
            print(f"Monitor {self.name} pkt_num: {self.pkt_cntr}\n")
            pkt_mon.print_packet()
        self.aport.append(pkt_mon)
        self.pkt_cntr += 1
        self.raw_data = []
        self.pkt_size = 0

    # ------------------------------------------------------------------
    # Abstract methods for subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def sample_data(self) -> tuple:
        """Sample data from the interface for one beat.

        Returns:
            tuple: (data_word: int, valid_bytes: int)
                data_word  — the masked data value for this beat
                valid_bytes — number of valid bytes in this beat
        """
        ...

    @abstractmethod
    def is_last(self) -> bool:
        """Return True if this beat is the last beat of the packet."""
        ...

    @abstractmethod
    def build_packet(self, pkt: Packet) -> None:
        """Fill the Packet object from accumulated raw_data and pkt_size.

        Called once per completed packet, before appending to aport.
        """
        ...


# ==============================================================================
# SingleCycleMonitorBase
# ==============================================================================

class SingleCycleMonitorBase(ABC):
    """
    Base monitor for single-cycle ready-valid interfaces.

    Each valid handshake is a complete transaction (one beat = one transaction).
    Subclasses implement sample_fields() to read named data fields into a dict.
    """

    def __init__(self, name: str, clk: SimHandleBase,
                 valid: Optional[SimHandleBase] = None,
                 ready: Optional[SimHandleBase] = None,
                 aport: list = None, verbose: bool = False):
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.clk = clk
        self.valid = valid
        self.ready = ready
        self.aport = aport if aport is not None else []
        self.verbose = verbose
        self.tnx_cntr = 0

    async def mon_if(self) -> None:
        """Forever-loop: await rising edge, check handshake, sample fields."""
        self.log.info(f"Starting {self.name} single-cycle monitor")
        while True:
            await RisingEdge(self.clk)

            if self.ready is None:
                tnx_completed = bool(self.valid.value)
            else:
                tnx_completed = bool(self.valid.value and self.ready.value)

            if tnx_completed:
                fields = self.sample_fields()
                if self.verbose:
                    self.log.info(f"[{self.name}] tnx {self.tnx_cntr}: {fields}")
                self.aport.append(fields)
                self.tnx_cntr += 1

    @abstractmethod
    def sample_fields(self) -> dict:
        """Read all data fields from the interface and return as a dict.

        Called once per handshake. Each key is a field name, each value
        is the sampled integer value.
        """
        ...


# ==============================================================================
# ReadyValidResponderBase
# ==============================================================================

class ReadyValidResponderBase:
    """
    Protocol-agnostic ready-signal controller.

    Implements different ready strategies using FlowControlMode.
    """

    def __init__(self, name: str, clk: SimHandleBase,
                 ready: Optional[SimHandleBase] = None,
                 config: ReadyValidConfig = ReadyValidConfig()):
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.clk = clk
        self.ready = ready
        self.config = config

    async def ready_ctrl(self) -> None:
        """Controls ready signal based on configured flow control mode."""
        self.log.info(f"Starting {self.name} responder")

        if self.ready is None:
            return

        while True:
            if self.config.flow_ctrl_mode == FlowControlMode.ALWAYS_ON:
                self.ready.value = 1
                await RisingEdge(self.clk)

            elif self.config.flow_ctrl_mode == FlowControlMode.RANDOM:
                # Active phase
                self.ready.value = 1
                active_cycles = random.randint(1, 10)
                for _ in range(active_cycles):
                    await RisingEdge(self.clk)

                # Backpressure phase
                self.ready.value = 0
                wait_cycles = random.randint(
                    self.config.backpressure_min_delay,
                    self.config.backpressure_max_delay
                )
                for _ in range(wait_cycles):
                    await RisingEdge(self.clk)

            else:
                # Default safe
                self.ready.value = 1
                await RisingEdge(self.clk)
