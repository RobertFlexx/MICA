# Verification entry points

BUILDING.md contains the complete commands. CTest runs the original integration,
frozen binary compatibility and fast-engine differential suites, generated-ISA
checks, engineering regressions and every published example's build. FIR results are
checked against an independent signed Python calculation. The three-file
startup/CRC/UART example is linked and executed. Infinite blink and watchdog wait
firmware are assembled; their specialized HDL tests provide event delivery.

Icarus executes 8 existing scalar/F/B/T tests, SRAM components, UART/GPIO/timer
firmware, scheduler, segmented ALU and the converted VHDL watchdog SoC. GHDL
executes the independent VHDL watchdog and CRC engine. `sim-peripherals` adds native
Verilog-2005 UART/FIFO tests, held CRC responses and 32/64-bit CRC/RX
interrupt/serial echo firmware. Verilator compares retirement events against the
reference under randomized bus stalls/latency. Formal tests cover ALU equivalence,
SRAM response ownership/stability/reset and bounded FIFO ordering, with explicit
assumptions in FORMAL.md. Generated drawings validate RTL signal names.

`-DMICA_FUZZ=ON` adds seeded libFuzzer ELF reader/writer/relocator tests under
Clang ASan/UBSan. Truncation, overflow, malformed relocation, expression depth,
invalid CSR and reserved encoding tests are permanent regressions. The original
v0.1 SDK comparison is skipped because that external SDK is unavailable.

Linux and macOS jobs pass in the [recorded implementation CI run](../engineering/results/ci.json).
Vivado implementation and physical-board checks need their own target environment.

## Current 2.0 checks

The [2.0 report](../engineering/MICA2_VERIFICATION.md) records new local runs.
`sim-mica2-32/64` execute compact operations. `sim-mica2-timer32/64` verify timer
wake, handler return and STOP stability. `verification/differential/mica2.py`
compares all three new profiles through 129 delayed-memory runs plus nine reset
replays, including compact branch/address boundaries and precise stack faults.
`scripts/verify.py --all` includes these stages, all seven synthesis mappings,
all drawing checks and the optional LLVM code-size stage. Current evidence is
separate from the historical 1.0 CI record above.
