# Verification entry points

BUILDING.md contains the complete commands. CTest runs the original integration,
frozen binary compatibility and fast-engine differential suites, generated-ISA
checks, engineering regressions and every published example's build. FIR results
are checked against an independent signed Python calculation. The three-file
startup/CRC/UART example is linked and executed. Infinite blink and watchdog
wait firmware are assembled; their specialized HDL tests provide event delivery.

Icarus executes 8 existing scalar/F/B/T tests, SRAM components, UART/GPIO/timer
firmware, scheduler, segmented ALU and the converted VHDL watchdog SoC. GHDL
executes the independent VHDL watchdog and CRC engine. `sim-peripherals` adds native Verilog-2005 UART/FIFO tests, held CRC responses and 32/64-bit CRC/RX interrupt/serial echo firmware. Verilator compares retirement events
against the reference under randomized bus stalls/latency. Formal tests cover
ALU equivalence, SRAM response ownership/stability/reset and bounded FIFO ordering, with explicit
assumptions in FORMAL.md. Generated drawings validate RTL signal names.

`-DMICA_FUZZ=ON` adds seeded libFuzzer ELF reader/writer/relocator tests under
Clang ASan/UBSan. Truncation, overflow, malformed relocation, expression depth,
invalid CSR and reserved encoding tests are permanent regressions. Report
skips explicitly: the old v0.1 external SDK comparison is unavailable locally.
MacOS/Vivado/physical board checks require their own execution environment.
