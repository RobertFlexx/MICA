# MICA 2.0
> ***Microcontroller Instruction Core Architecture***

MICA is an experimental 32-bit and 64-bit processor architecture for embedded
systems. It uses mixed 16-bit and 32-bit instructions and comes with a C++23
toolchain, an emulator, a multicycle SystemVerilog CPU and an Arty A7 SoC target.
The SDK includes assembly libraries, firmware, tests and editable hardware drawings.

Version 2.0 adds compact stack accesses, a two-byte counted branch, PC-relative
addressing and wakeable `wfi`. MICA-2C keeps eight register slots; MICA-2E and
MICA-2L offer sixteen. The 1.0 compatibility mode and all 14 frozen firmware
fixtures are preserved.

With F enabled, MICA's byte-copy loop takes **6 bytes, versus 16 for RV32IC or 12 with Zcb**:
50–62.5% less code for that loop. It also takes three instructions instead of
six. The [comparison](docs/research/RISCV_COMPARISON.md) includes the assembly
and a stack-access example where both architectures tie.

## Build and run

The software needs CMake 3.20+, Python 3.10+, and GCC or Clang with C++23 and
`__int128` support.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
build/mica-as --profile MICA-2C examples/mica2_short32.mica -o short.bin
build/mica-run --profile MICA-2C short.bin
```

The example runs a counted loop and leaves `x1=28`.

For separately assembled MICA 2.0 firmware, the `ADRPC16` relocation lets
`adrpc` refer to symbols in another object without new machine-code encodings.
The [linker guide](docs/toolchain/LINKER.md) includes reproducible MICA-32 and
MICA-64 examples. ELF files retain the ISA revision: `mica-run --mica2` executes
2.0 ELF, while mismatched 1.0/2.0 objects or runtime modes are rejected.
Compact `dbnz.s` loops also support separate compilation through `PCREL6`;
the linker checks their range and preserves requested data alignment.

For a first program, save this as `hello.mica`:

```asm
.arch mica32v2
li8 a0,21
add a0,a0
stop
```

Assemble with `build/mica-as --mica2 hello.mica -o hello.bin`, then run
`build/mica-run --mica2 hello.bin`. The register dump reports `x1=0x2a`.
Use `stop` to end a test and `wfi` to sleep until a pending event wakes the core.

## Components

| Component | Current implementation |
| --- | --- |
| CPU | 32/64-bit scalar multicycle core, compact loops, precise traps, timer interrupts and fetch-word reuse |
| Memory and devices | Synchronous SRAM, GPIO, UART TX/RX with FIFO and an optional VHDL CRC-32 engine |
| Tools | `mica-as`, `mica-ld`, `mica-dis`, `mica-run`, `mica-objdump`, `mica-nm`, `mica-objcopy` |
| Firmware | Linked startup and CRC, UART echo, FIR filtering, scheduler, compact loops and timer wake tests |
| Verification | Retirement comparison, randomized memory latency, HDL simulations, component formal checks, sanitizers and fuzzing |
| Hardware target | Arty A7-100 board top, pin constraints and Vivado build script; board-top simulation passes |

Each tool has `--help`. `mica-run --profile MICA-2E` selects the expanded 32-bit
configuration; `--debug` opens the emulator debugger. Enable 2.0 in hardware
with `MICA2=1`. Board defaults retain the 1.0 firmware configuration.

## Hardware and project status

[BUILDING.md](BUILDING.md) covers HDL dependencies and the full regression.
RTL simulation, retirement comparisons, component formal checks and Yosys
mapping pass. The [verification report](docs/engineering/MICA2_VERIFICATION.md)
records the results. The [Arty guide](docs/hardware/FPGA_BUILD.md) covers the
board build and serial console.

Vivado implementation, timing closure and physical board boot still need testing.
Power use and maximum clock speed are still unmeasured.

The SDK supports assembly development. A C compiler backend, pipelined core,
protected tasks and multicore RTL are still needed. SIMD and atomic operations
have emulator implementations. The [status table](SDK_STATUS.md) covers the
remaining work.

## Documentation

Start at the [documentation index](docs/README.md). The
[2.0 ISA guide](docs/architecture/MICA2.md) describes the new instructions and
links to the [1.0 compatibility manual](docs/architecture/ISA.md).
The [assembler guide](docs/toolchain/ASSEMBLER.md) covers writing programs;
[hardware drawings](docs/hardware/DATAPATH.md) show the RTL connections.
Contribution guidelines are in [CONTRIBUTING.md](CONTRIBUTING.md).

MICA is released under the [MIT license](LICENSE).

The [roadmap](docs/ROADMAP.md) defines the compiler, core implementation and
physical validation milestones for the embedded platform.
