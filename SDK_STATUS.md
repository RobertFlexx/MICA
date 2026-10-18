# MICA 1.0 support status

Engineering revision r2 supports assembly development on the reference emulator
and transactional scalar RTL. The table distinguishes implemented features from
the next work in each area. Detailed results are in the
[implementation report](docs/engineering/IMPLEMENTATION_REPORT.md).

| Area | Available | Next work |
| --- | --- | --- |
| Scalar ISA | Documented 32/64-bit encodings, M/F/B/T, profile and CSR discovery, frozen firmware fixtures | Exhaustive long-encoding execution coverage |
| Toolchain | Seven C++23 tools, ELF image objects, nine relocations, linking, inspection and conversion | Independent sections/NOBITS, parser diagnostics, relaxation, broader ELF support |
| Emulator | Reference and fast interpreter, specialized counted loops, traps, timer, traces, CLI debugger | General JIT, cycle-stepped platform model, GDB RSP, multiple harts |
| RTL | Multicycle scalar core, 8/16 registers, 32/64-bit data, precise commit/traps, fetch reuse | Pipeline, user protection/MPU, vector/atomic/multicore hardware |
| Memory | Variable-latency protocol, faults, stalls/reset tests, synchronous byte-write SRAM | External fabric bridges, coherent DMA, caches |
| Firmware | Linked startup/CRC/UART, scalar FIR, GPIO/timer self-test, two-task scheduler, RX interrupt echo | General RTOS runtime, protected tasks, ROM-copy startup, C compiler and library |
| HDL components | SystemVerilog CPU/SoC; Verilog SRAM, UART RX and FIFO; VHDL watchdog and CRC | Vendor mixed-language implementation on a physical target |
| Verification | GCC/Clang sanitizers, randomized retirement comparison, 14 frozen images, small proofs, bounded FIFO check, fuzz target | Whole-CPU formal properties, wider interrupt coverage, longer fuzz campaigns |
| FPGA | Arty A7-100 pin mapping, actual board-top simulation, Yosys mapped configurations | Vivado synthesis/P&R, timing closure, physical boot and power |
| Research | Fetch transactions/cycles and standalone ALU activity/area | Physical energy/timing, equivalent external-core comparisons, banking/event/loop experiments |
| SDK and CI | Checked drawings, source/binary archives, Linux and macOS CI | Additional host coverage and external engineering review |

MICA-DSP runs in the emulator; its SIMD datapath is still software-only.
MICA-MP is a proposed configuration and is rejected by profile selection.
The current hardware has one uncached hart in machine mode. The assembly
runtime and prospective C header support that environment; compiler integration
and C language conformance remain separate work.

The ISA version and machine-code compatibility remain MICA 1.0. The
[recorded CI run](docs/engineering/results/ci.json) identifies the tested
implementation commit and all seven successful jobs.
