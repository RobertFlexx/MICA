# MICA 1.0 status

## Run successfully

- GCC C++23 Release build and Clang C++23 sanitizer build.
- Three CTest targets: integration, frozen firmware compatibility, accelerated-engine differential tests.
- Ten unchanged firmware images against shipped binary fixtures.
- Randomized 32/64-bit scalar behavior, counted-loop translation, extension fallback, assembler negative cases, and the new freestanding reduction example.
- Four new Graphviz engineering drawings rendered to SVG and PNG.
- Local benchmark script with checked machine state, median-of-three results on AMD EPYC 9V74.

## Supplied but not verified locally

- The existing scalar SystemVerilog CPU and its testbench suite.
- A standalone Verilog synchronous SRAM and testbench.
- A standalone VHDL-2008 watchdog and testbench.
- Continuous integration jobs for HDL simulation and SRAM synthesis. GitHub Actions will need to run them before a green CI badge is warranted.

## Explicitly missing

- A memory response handshake, precise bus faults and an FPGA BRAM-integrated CPU.
- Actual physical Fmax, dynamic/leakage power, energy/task and a board boot test.
- Production quality privilege/MPU, coherent atomic multicore, SIMD hardware, an ELF toolchain or ISO C/C++ runtime.
- A general JIT compiler. The native translator covers only one safe counted loop shape.

## Engineering priorities

1. Run HDL CI and fix anything it flags.
2. Introduce a wait-state capable, precisely retiring fetch/LSU interface.
3. Use reference-model co-simulation to test every RTL instruction after that interface change.
4. Build a fair on-board energy and timing comparison to Ibex/CV32E40P/PicoRV32.
5. Add relocatable ELF objects, a linker, debugger protocol, compiler ABI and proper libc before using the word production.
