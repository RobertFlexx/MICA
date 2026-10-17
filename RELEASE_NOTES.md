# MICA 1.0 engineering update

Date: October 17, 2026

This is a revision of the SDK, not a new ISA version. Original 1.0 binary encodings are retained and the ten frozen images continue to match.

## Changed

- A fast C++23 interpreter path for common 16-bit scalar instructions and F counted branches, with reference fallback.
- A specialized native loop translator for safe `addi` / `dbnz` pairs, preserving the reference retired-instruction and register state.
- Independent deterministic differential tests for 32-bit and 64-bit accelerated execution and extension fallback.
- `.assert`, `.error`, circular-include detection, a limit on expanded source, and `--map` output for the assembler.
- Two portable source modules: Verilog synchronous word SRAM and VHDL windowed watchdog. Both have HDL testbench sources, but were not locally HDL-simulated.
- New freestanding byte-reduction routines and an executable example.
- Four signal- and protocol-oriented engineering drawings, with editable Graphviz sources.
- A CI matrix for Linux GCC, Linux Clang, macOS Clang, sanitizers, HDL tests, optional synthesis and benchmark artifacts.
- A research plan with measurable rejection criteria instead of slogans.

## Verified locally

- Release C++23 build with GCC, CTest software integration, fixed binary firmware compatibility and fast/reference differential tests.
- Debug Clang AddressSanitizer/UndefinedBehaviorSanitizer build and CTest software checks.
- Measured small counting-loop microbenchmark on AMD EPYC 9V74. See `docs/ENGINEERING_REVISION.md` and `docs/emulator_benchmark_epyc_2026-10-17.json`.
- Graphviz SVG/PNG rendering of the added diagrams.

## Not verified locally

- The HDL simulation, synthesis and FPGA timing jobs in GitHub Actions have not run here because Icarus, GHDL and Yosys were not installed.
- No real PCB, MPU, linker, compiler backend, multicore coherency, full standard library or chip fabrication.
- No general 1,000 MIPS emulator claim. The measured >3,000 MIPS figure is for one specialized native loop pattern.
