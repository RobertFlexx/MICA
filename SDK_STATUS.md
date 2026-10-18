# MICA 1.0 engineering r2 status

| Area | Implemented and exercised | Remaining acceptance work |
| --- | --- | --- |
| Scalar ISA | Normative32/64-bit encodings, M/F/B/T, profile/CSR discovery; frozen binaries | Exhaustive long-encoding execution coverage |
| Toolchain | Seven C++23 tools, real ELF image objects, nine relocations, linking, inspection, conversion | Independent sections/NOBITS, richer parser/diagnostics, relaxation, general ELF compatibility |
| Emulator | Reference, existing short fast interpreter/count-loop translator, precise traps, timer, traces, CLI debugger | General JIT, cycle-accurate platform engine, GDB RSP, multicore simulation |
| RTL | Transactional scalar reference,8/16 registers,32/64-bit data, precise commit/traps, fetch reuse | Pipelined implementation, user/MPU, vector/atomic/multicore hardware |
| Memory | Variable-latency core protocol, faults, stalls/reset tests, synchronous byte-write Verilog SRAM | External fabric bridges, coherent DMA, caches |
| Firmware | Linked startup/CRC/UART, scalar FIR, GPIO/timer self-test, two-task timer scheduler, CRC/RX interrupt echo | General RTOS qualification, protected tasks, ROM-copy startup, C compiler/libc |
| Languages | SystemVerilog CPU/SoC, portable Verilog SRAM/UART RX/FIFO, GHDL VHDL watchdog/CRC with converted-netlist SoC tests | Vendor mixed-language physical integration |
| Verification | GCC/Clang sanitizers, randomized retirement comparison,14 frozen images, two small proofs, bounded FIFO check, fuzz target | Whole-CPU formal proof, exhaustive interrupt placements, extended fuzz campaigns |
| FPGA | Arty A7-100 pins checked against vendor XDC, SoC/UART simulation, Yosys mapped profiles | Vivado synthesis/P&R/timing execution, physical board boot and power |
| Research | Measured fetch transactions/cycles and standalone ALU activity/area | Physical energy/timing, independent ISA baselines, banking/events/loop hardware |
| Release | Generated ISA/drawings, editable DOT/SVG/PDF, CI commands and packaging | Target GitHub/macOS runs, external engineering review |

The implementation report contains exact commands, measurements, logs and known
limitations. No architecture/version number was changed. Machine code remains
MICA 1.0. MICA-MP is a non-runnable proposal; MICA-DSP is emulator-only. Hardware
completion, one-IPC performance, physical timing closure and energy superiority
are not claimed. The assembly runtime is not an ISO C/C++ standard library.
