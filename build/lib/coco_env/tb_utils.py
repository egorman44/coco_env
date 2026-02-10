from cocotb.triggers import RisingEdge
from cocotb.triggers import FallingEdge
from cocotb.triggers import Timer    
from cocotb.utils import get_sim_time
    
async def reset_dut(reset, duration_ns, positive = 0):
    reset.value = 0 ^ positive
    await Timer(duration_ns, units="ns")
    reset.value = 1 ^ positive
    reset._log.debug("Reset complete")

async def custom_clock(clk, delay = 100):
    high_delay = low_delay = delay
    while True:
        clk.value = 1
        await Timer(high_delay, units="ns")
        clk.value = 0
        await Timer(low_delay, units="ns")

async def watchdog_set(clk, comp, limit=100000):
    watchdog = 0
    while(len(comp.port_prd) != len(comp.port_out)):
        await RisingEdge(clk)
        watchdog += 1
        if(watchdog == limit):
            print(f"[WARNING] Watchdog has triggered.")
            break

async def assert_signal(clk, reset, signal, correct_value=0):
    while True:
        if signal.value == correct_value or reset == 1:
            await RisingEdge(clk)
        else:
            print(f"time= {get_sim_time(units='ns')}")
            assert False , f"[TEST_FALIED] signal {signal._name} was asserted"
    
