# MICA 1.0
> ***Microcontroller Instruction Core Architecture***

MICA is an experimental 32-bit and 64-bit processor architecture for embedded
software. It uses mixed 16-bit and 32-bit instructions and has a C++23 toolchain,
a reference emulator, a multicycle SystemVerilog CPU and an Arty A7 SoC target.
The repository includes assembly libraries, firmware, simulation tests and
editable hardware drawings.

The design work focuses on compact programs, useful embedded operations and
reducing unnecessary hardware activity. Workload results and implementation
costs guide that work. The [published measurements](docs/research/BENCHMARKS.md)
cover the current implementation; comparisons with other processors are still
open work.

The ISA remains **MICA 1.0**. Engineering revision **r2** preserves the existing
instruction encodings and all 14 firmware compatibility fixtures.

## Build and run

The software needs CMake 3.20+, Python 3.10+, and GCC or Clang with C++23 and
`__int128` support.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
python3 scripts/build_firmware.py --tools build
build/mica-run build/firmware/linked.elf
```

The linked example initializes the assembly runtime, clears BSS, computes
CRC-32 and prints `MICA linked CRC OK` through the emulated UART. The current
SDK supports assembly development; a C compiler backend is still needed.

For a smaller first program, save this as `hello.mica`:

```asm
.arch mica32
li8 a0,21
add a0,a0
wfi
```

Assemble with `build/mica-as hello.mica -o hello.bin`, then run
`build/mica-run hello.bin`. The register dump reports `x1=0x2a`.
For now, `wfi` halts until reset. It is exceptionally good at waiting.

## What is here

| Component | Current implementation |
| --- | --- |
| CPU | 32/64-bit scalar multicycle core, precise traps, timer interrupts and fetch-word reuse |
| Memory and devices | Synchronous byte-write SRAM, GPIO, UART TX/RX with a FIFO, and an optional VHDL CRC-32 engine |
| Tools | `mica-as`, `mica-ld`, `mica-dis`, `mica-run`, `mica-objdump`, `mica-nm`, `mica-objcopy` |
| Firmware | Linked startup and CRC, interrupt-driven UART echo, FIR filtering, self-test and a two-task timer scheduler |
| Verification | Retirement comparison, randomized memory latency, HDL simulations, small formal checks, sanitizers and fuzzing |
| Hardware target | Arty A7-100 board top, constraints and a Vivado build script; board-top simulation passes |

Each tool has `--help`. `mica-run --profile MICA-E` selects the expanded 32-bit
configuration; `--debug` opens the emulator debugger. The reference interpreter
is the default. `--fast` and the specialized `--native-loops` engine are also
available.

## Hardware and project status

[BUILDING.md](BUILDING.md) covers HDL dependencies and the full regression.
The [Arty guide](docs/hardware/FPGA_BUILD.md) describes the board image, serial
console and build flow. The SoC and actual board top have been simulated;
Vivado implementation, timing closure and physical board boot remain unverified.

The next substantial hardware work is a pipelined core, followed by broader
protection and extension support. The current scheduler runs trusted machine-mode
tasks. SIMD and atomic operations have emulator implementations; their RTL and
multicore support remain open. The [status table](SDK_STATUS.md) records these
boundaries in detail.

## Documentation

Start at the [documentation index](docs/README.md). The
[ISA manual](docs/architecture/ISA.md) defines architectural behavior, and the
[toolchain guide](docs/toolchain/ASSEMBLER.md) covers assembly development.
[Hardware drawings](docs/hardware/DATAPATH.md) include editable sources and
connections checked against the RTL.

The [audit](docs/engineering/AUDIT.md) records the original defects. The
[r2 implementation report](docs/engineering/IMPLEMENTATION_REPORT.md) collects
repairs, test results, measurements and remaining work. Contribution guidelines
are in [CONTRIBUTING.md](CONTRIBUTING.md).

MICA is released under the [MIT license](LICENSE).
