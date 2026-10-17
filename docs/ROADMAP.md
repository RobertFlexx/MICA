# MICA roadmap after the 1.0 SDK

This is a development ordering, not a product announcement.

## First: trust the hardware

Run iverilog and Verilator on the RTL with deterministic memory images, then inspect store byte lanes, both XLEN modes, the F pointer semantics, faults, and every reserved opcode. Write a commit trace out of RTL and compare it against `mica-run` over thousands of random legal programs. Introduce a ready/valid/error handshake for fetch and data before considering synchronous block RAM. On FPGA, replace the asynchronous byte array with a BRAM-friendly implementation and measure actual resource utilization and Fmax.

## Second: real software deployment

Define an executable header or ELF ABI with XLEN, extension bitmap, ROM image requirements and address relocs. Add ELF objects, a linker and a disassembler with symbol support. Write a backend for LLVM or GCC and a compiler-linkable freestanding C runtime. Maintain a stable test corpus for ABI calling conventions. Add one debugger interface and a small monitor shell.

## Third: real embedded controls

Specify and implement trap entry, timer interrupts, interrupt priority, safe `wfi`, a simple MPU, ROM boot and a watchdog. Once these work, port a compact RTOS with a context-switch conformance test. The important power test is the current consumed in a timer-driven sleep cycle. Nothing called "low-power" is complete until measured.

## Fourth: dedicated SIMD silicon

Take one representative DSP kernel through several physical vector-lane widths. Compare a 128-bit combinational engine against 64-, 32- and 16-bit segmented execution, all running the exact same ISA tests. Add per-lane operand isolation, clock enables and activity counters. Energy measurements decide the winner.

## Fifth: multicore

Define memory consistency, bus arbitration, DMA visibility and the progress guarantee for LR/SC. Test two physical harts, add coherent shared memory and independent timer/interrupt sources. Port and verify an actual multitasking workload. Until this stage, the A emulator is not evidence of working multicore silicon.

## Sixth: challenge known cores

Build the same workloads for MICA32 and a comparable Ibex RV32EC core. Use equal memory, clock, synthesis and FPGA conditions. Report bytes, cycles, Fmax, area, energy per useful task, interrupt latency and sleep current. Document failures as carefully as successes. Only claim a breakthrough if independent measurements make it defensible.
