# MICA 1.0
> *Microcontroller Instruction Core Architecture*

MICA is an experimental 32/64-bit RISC architecture for embedded systems. It has its own compact machine code, a C++23 assembler and disassembler, a functional emulator, freestanding assembly routines, and a small SystemVerilog CPU.

The 1.0 tag stays put. This SDK update fills in missing work without changing the existing 1.0 instruction encodings. New instructions are all opt-in.

## Build

```sh
cmake -S . -B build
cmake --build build -j
ctest --test-dir build --output-on-failure

build/mica-as --xlen 64 --bitops examples/bitops64.mica -o /tmp/bit.bin
build/mica-dis --xlen 64 /tmp/bit.bin
build/mica-run --xlen 64 --bitops /tmp/bit.bin
```

Python 3 and a C++23 compiler are needed for the tests and programs. GCC and Clang can build the tools. The SIMD emulator uses a GCC/Clang `__int128` extension.

## Profiles

| Feature | Purpose | Software model | Reference scalar RTL |
| --- | --- | --- | --- |
| 32/64-bit scalar | two architectures, same short encoding | yes | prototype |
| X | 16 scalar registers | yes | parameter |
| M | integer multiply | yes | parameter |
| F | streaming pointer updates, counted loop | yes | prototype |
| B | bits, rotates, min/max, byte swap | yes | prototype |
| T | machine-level `ecall`/`eret`, pending interrupt | yes | prototype |
| A | atomic read-modify-write | single-core emulator | not implemented |
| V | 128-bit packed SIMD | emulator | not implemented |

The base is still eight named registers, with a 16-bit common instruction format and 32-bit escapes. XLEN64 includes explicit sign-extending 32-bit arithmetic. Neither a scheduler nor a general-purpose OS is included.

## New things in this SDK update

- MICA-B: 20 bit-manipulation instructions with exact XLEN32/64 behavior. The assembler and disassembler know their encodings, the interpreter executes them, and the optional RTL datapath has matching operations.
- MICA-T: explicit trap state, handler return, software-pending interrupts, and an external `irq_i` on the RTL core. It does not pretend to be an MPU or a user/kernel architecture.
- Hardware discovery: `features` and `arch` CSRs. `instret_lo` and `instret_hi` expose retired instruction counts in the emulator, and in RTL with the optional `PERF=1` parameter. Cycle measurements still need real hardware.
- More assembly modules: bit helpers, buffer XOR, full-scan byte comparison, and explicit byte clearing.
- A/B software tests, HDL testbench sources for B/T, new connection drawings, and a research program with measurable go/no-go criteria.

## Important limits

The software integration tests and byte compatibility checks have been executed. The HDL files are intended for FPGA simulation and synthesis, but no HDL simulator was available during this update. No FPGA timing, power, or ASIC silicon result is claimed. The current FPGA SoC still has asynchronous memory reads and no ready/valid wait-state interface. Atomics and SIMD are emulator-only. Trap handling is minimal and doesn't intercept illegal memory operations. There is no C compiler backend, object linker, ISO C library, virtual memory, coherent multicore, or finished physical PCB.

A short instruction and a high clock do not automatically make a processor efficient. MICA has to beat properly configured RISC-V, CORE-V and Arm-class alternatives in measured energy per task before anyone can claim an edge.

## Read this first

- [ISA](docs/ISA.md) and [B/T extension contract](docs/EXTENSIONS.md)
- [Assembly dialect](docs/DIALECT.md) and [ABI](docs/ABI.md)
- [Freestanding runtime](docs/RUNTIME.md)
- [Microarchitecture](docs/MICROARCH.md) and [hardware integration](docs/HARDWARE.md)
- [Schematics](docs/SCHEMATICS.md), [research program](docs/RESEARCH_PROGRAM.md) and [older research notes](docs/RESEARCH.md)
- [Verification](docs/VERIFICATION.md), [current status](SDK_STATUS.md) and [release notes](RELEASE_NOTES.md)

All original sources and tests are included. MIT license. External architecture documentation is used as reference material, not bundled implementation code.

## Reproducible micro-benchmark

`python3 benchmarks/compare_bitops.py` compares a portable scalar popcount loop with B's `popcnt3`, including setup and call overhead. The fixed input produces 200 versus 6 retired instructions and 32 versus 20 binary bytes. This isolates one task where B helps instruction traffic. It is not a measured energy or clock-speed result.
