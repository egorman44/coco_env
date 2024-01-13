from cocotb.triggers import Timer

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
