# MICA 1.0

A small 32/64-bit processor architecture with its own machine code, assembler, functional emulator, assembly runtime, SystemVerilog core, and FPGA bring-up files.

MICA started as a question: what if the cheap instructions were the operations small embedded programs actually use, instead of making a full-size CPU mandatory? Version 1.0 keeps the 16-bit scalar encoding, 8-register minimum, and optional wider extensions. It adds **F**, a compact flow extension for byte/halfword/word/quadword streaming operations and counted loops. F has actual encodings, C++23 execution support, and a first-pass RTL implementation.

The reference CPU is still a multicycle design. It is not a polished commercial CPU or a measured replacement for RISC-V. The ISA is distinct from RISC-V. The flow operations are a distinct MICA encoding and set of semantics, not a claim to have invented post-increment loads or decrement-and-branch.

## Build and run

Requirements: CMake 3.20+, GCC or Clang capable of C++23, Python 3 for tests. SIMD's reference arithmetic uses `__int128` (GCC/Clang extension). The assembler itself only uses ISO C++23.

```sh
cmake -S . -B build -G Ninja
cmake --build build
ctest --test-dir build --output-on-failure

build/mica-as --xlen 32 --flow examples/flow_copy32.mica -o /tmp/flow.bin
build/mica-run --xlen 32 --flow /tmp/flow.bin

build/mica-as --xlen 64 --flow examples/flow_copy64.mica -o /tmp/flow64.bin
build/mica-run --xlen 64 --flow /tmp/flow64.bin
```

The `mica-dis --xlen 32 image.bin` tool prints decoded addresses, instructions and bytes from raw binary images.

The emulator starts at address 0, allocates 1 MiB RAM by default, and prints registers at halt. `wfi` and `ecall` halt this prototype instead of doing privileged exception entry. Use `--help` on both tools for options.

## What is in 1.0

| Part | Delivered today | Not delivered |
| --- | --- | --- |
| ISA | 16-bit common instructions, 32-bit extension envelope, 32/64-bit scalar, F extension | Frozen production ABI, virtual memory |
| Assembler | C++23, two passes, labels, expressions, macros, includes, typed SIMD syntax, raw binary, Intel HEX, listing; plus mica-dis disassembler | ELF relocatable objects, system linker |
| Emulator | C++23 functional interpreter, M, X, A, V, F execution, MMIO | Cycle accuracy, coherence, user/kernel separation |
| Runtime | Freestanding assembly string, memory, math, console, atomic, flow and checksum routines | ISO C/C++ libc, C compiler, dynamic allocation/runtime loader |
| RTL | Multicycle XLEN32/64 scalar, F operations, minimal UART TX + LEDs | SIMD RTL, A RTL, MPU, interrupts, low-power measured silicon |
| Hardware | Arty A7 wrapper, board pins, signal diagrams, generated ROM files | Guaranteed FPGA bitstream, timing reports, PCB fabrication files |
| Verification | End-to-end software tests and smoke-test HDL sources | Executed HDL simulation, formal equivalence, measured Fmax/watts |

This is a **1.0 SDK release**, not a production ISA ratification. Hardware work is at prototype maturity. Read [SDK_STATUS.md](SDK_STATUS.md) before trusting a feature in RTL.

## Architecture in a paragraph

MICA32 and MICA64 use 32- or 64-bit scalar registers. Most short instructions read and write three-bit register names, so x0..x7 are enough for the smallest implementation. x0 is zero, x6 is the link register and x7 is the stack pointer. A 32-bit escape carries three-register operations, long branches, atomics, SIMD and 64-bit-specific operations. Most instructions work the same way in 32-bit and 64-bit mode. MICA64 has explicit signed-extended W operations for math that wants 32-bit results. Everything is little-endian.

The extra F instructions reduce common inner-loop instruction traffic. For example, a `memcpy` byte iteration with an ordinary loop uses six short instructions (12 bytes). The F version uses two short streaming operations and one extended `dbnz` (three instructions, eight bytes). That is an **instruction count and encoding** result; it is not an energy measurement.

## The actual developer workflow

1. Choose an ISA profile, XLEN 32 or 64, and options such as `--flow` or `--simd`.
2. Write `.mica` source using the [dialect manual](docs/DIALECT.md).
3. Assemble to raw firmware, optionally emit `.hex` and `.lst`.
4. Check the firmware in `mica-run` with a step limit and optional trace.
5. Run `tests/integration.py` after modifying the assembler or simulator.
6. Only then attempt an FPGA build. The [Arty board guide](boards/arty_a7/README.md) describes the I/O mapping and its limitations.

Documentation: [ISA](docs/ISA.md), [ABI](docs/ABI.md), [microarchitecture](docs/MICROARCH.md), [runtime](docs/RUNTIME.md), [schematics](docs/SCHEMATICS.md), [hardware](docs/HARDWARE.md), [research](docs/RESEARCH.md), [verification](docs/VERIFICATION.md), [benchmarks](docs/BENCHMARKS.md).

## Why bother?

A tiny base CPU can avoid a lot of architectural baggage, and a carefully chosen short instruction can reduce fetch traffic. On the other hand, eight registers often means extra spills, MICA's 32-bit escapes are comparatively expensive in the current multicycle implementation, and RISC-V's compressed and embedded profiles have a significant head start. The interesting experiment is whether the combination gives a better *energy per completed embedded workload* once both systems are equally optimized.

See the [research notes](docs/RESEARCH.md) for lowRISC Ibex, RISC-V compressed, CORE-V hardware loops, and MCU power benchmarking. We want proper A/B data, not processor fandom.

MIT-licensed SDK source. Third-party links are references, not bundled derivatives.
