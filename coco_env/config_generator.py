import itertools
from dataclasses import dataclass
from typing import List, Iterator

from .rv_base import DriverConfig, ResponderConfig, FlowControlMode

@dataclass
class FlowControlConfig:
    """A single combination of flow control parameters."""
    driver_config: DriverConfig
    responder_config: ResponderConfig
    pkt_delay_min: int
    pkt_delay_max: int


class FlowControlGenerator:
    """
    Generates all combinations of DriverConfig, ResponderConfig, and pkt_delay.
    """
    def __init__(self):
        # Default lists built with varying behaviors useful for standard stress testing.
        self.driver_configs: List[DriverConfig] = [
            DriverConfig(flow_ctrl_mode=FlowControlMode.ALWAYS_ON),
            DriverConfig(flow_ctrl_mode=FlowControlMode.ONE_VALID_ONE_NONVALID),
            
            DriverConfig(
                flow_ctrl_mode=FlowControlMode.RANDOM,
                tvalid_low_limit=3,
                tvalid_high_limit=1
            ),
            DriverConfig(
                flow_ctrl_mode=FlowControlMode.RANDOM,
                tvalid_low_limit=1,
                tvalid_high_limit=5
            ),
        ]
        
        self.responder_configs: List[ResponderConfig] = [
            ResponderConfig(flow_ctrl_mode=FlowControlMode.ALWAYS_ON),
            ResponderConfig(
                flow_ctrl_mode=FlowControlMode.RANDOM,
                backpressure_min_delay=1,
                backpressure_max_delay=5
            ),
        ]
        
        # delays (min, max) between packets
        self.pkt_delays: List[tuple[int, int]] = [(0, 0), (5, 15), (20, 50)]

    def add_driver_config(self, config: DriverConfig) -> None:
        self.driver_configs.append(config)

    def add_responder_config(self, config: ResponderConfig) -> None:
        self.responder_configs.append(config)
        
    def add_pkt_delay(self, delay: tuple[int, int]) -> None:
        self.pkt_delays.append(delay)
        
    def generate(self) -> Iterator[FlowControlConfig]:
        """
        Yields every combination of driver config, responder config, and pkt_delay tuples.
        """
        for d, r, p in itertools.product(self.driver_configs, self.responder_configs, self.pkt_delays):
            yield FlowControlConfig(driver_config=d, responder_config=r, pkt_delay_min=p[0], pkt_delay_max=p[1])
