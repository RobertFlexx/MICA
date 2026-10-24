# Embedded demonstrators

## Compiled sensor node

`compiler/examples/sensor_node.c`, its volatile-MMIO platform layer and
`firmware/examples/sensor_start32.mica` form a finite MICA-2E workload. Four timer
wakeups read simulated SRAM sensor samples, calculate CRC-8 packets, increment a
volatile measurement count, transmit UART bytes and kick the watchdog.

Run `python3 scripts/test_sensor_demo.py --tools build` with Clang, Icarus and
GHDL. The script builds two C objects and startup, links ELF, executes three
emulator modes, converts the VHDL watchdog and simulates the SoC with register
parity enabled. UART pins must emit the independently calculated packets.
Results include cycles, active/sleep clocks, observed interrupt entry, ROM bytes
and selected-signal transition counts. The timer is armed 2,000 clocks ahead
of each wait; this is a relative wake schedule, not a hard periodic deadline.
The testbench clock is 100 MHz while UART's configured divider is 16 clocks/bit;
it is a functional timing test, not a board operating point.

Stable sleep intervals issue no bus requests. Registered datapath signals are
quiet while timer and clock still toggle. Transition counts omit state boundaries
and exclude routing glitches, capacitance and clock-tree effects. No energy or
battery-life result follows from this measurement. There is no physical clock
gate or power domain in the reference SoC.

## Industrial and remote fault probes

`examples/mica2_watchdog32.mica` tests watchdog expiry, interrupt wake, clear and
resume on both XLEN configurations through `scripts/test_peripherals.py`.
The [fault campaign](RELIABILITY.md) compares protected and unprotected registers.
These are working supervision and fault probes, not a completed industrial
controller: memory protection, actuator safe-state policy, reset recovery,
bounded fabric waits and deadline analysis are absent.

## Signed DSP stream

`stdlib/dsp32_flow.mica` computes a signed 16-bit dot product with precise signed
post-increment loads and a compact counted branch. `benchmarks/core_revision.py`
compares it to `stdlib/dsp32.mica`, validates an independent host sum and compares
all retirement effects under five stall seeds. Existing FIR firmware remains in
the standard regression. This is a DSP kernel evaluation, not a complete audio
device. Packed DSP, vector RTL, circular-buffer hardware, sample-rate guarantees
and matched Cortex-M4/RISC-V DSP cycle comparisons remain open.

Security isolation, secure boot, key storage, authenticated updates and debug
authentication are not implemented. MICA-2S remains proposed. SRAM initialization
is ordinary writable memory and is not a root of trust.
