# MICA 2.0
> ***Microcontroller Instruction Core Architecture***

MICA is a 32/64-bit processor architecture for embedded software, with mixed
16-bit and 32-bit instructions, a C++23 toolchain, an emulator, a transactional
SystemVerilog CPU and an Arty A7 SoC target. The design concentrates on compact
counted loops, post-increment memory operations and a small register budget.

**MICA has a demonstrated code-size advantage over standard compressed RISC-V
on counted memory loops.** Its byte-copy loop is 6 bytes: **62.5% smaller than
RV32IC and 50% smaller than RV32IC with Zcb**. Those numbers come from actual
assembler output, including compressed RISC-V byte accesses. The
[comparison](docs/research/RISCV_COMPARISON.md) includes the sources, exact scope,
and a stack-access case where both compressed architectures tie.

## Build and run

Requires CMake 3.20+, Python 3.10+, and GCC or Clang with C++23 and `__int128`.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
build/mica-as --profile MICA-2C examples/mica2_short32.mica -o short.bin
build/mica-run --profile MICA-2C short.bin
```

The example leaves `x1=28`. It occupies 16 bytes, versus 18 for the equivalent
MICA 1.0 example; the 64-bit version shrinks from 22 to 16 bytes.

For a first program, save this as `hello.mica`:

```asm
.arch mica32v2
li8 a0,21
add a0,a0
stop
```

Assemble with `build/mica-as --mica2 hello.mica -o hello.bin`, then run
`build/mica-run --mica2 hello.bin`. The register dump reports `x1=0x2a`.
In 2.0, `stop` terminates a test; `wfi` sleeps until a pending event wakes it.

## What is here

| Component | Current implementation |
| --- | --- |
| CPU | 32/64-bit multicycle scalar core, precise traps, timer interrupts, fetch-word reuse, compact stack accesses and counted branches |
| Profiles | MICA-2C: 32-bit, eight register slots; MICA-2E: 32-bit, sixteen; MICA-2L: 64-bit, sixteen |
| Memory and devices | Synchronous byte-write SRAM, GPIO, UART TX/RX with FIFO, optional VHDL CRC-32, separately tested watchdog |
| Tools | `mica-as`, `mica-ld`, `mica-dis`, `mica-run`, `mica-objdump`, `mica-nm`, `mica-objcopy` |
| Firmware | Startup/CRC/UART, interrupt-driven echo, FIR, scheduler, compact loops and timer sleep/wake tests |
| Verification | HDL simulation, retirement comparison with bus stalls, component formal checks, mapped synthesis and software regressions |
| Drawings | Updated DOT, SVG, PNG and PDF at every existing schematic path, with RTL port checks and artifact hashes |

The legacy profiles and 14 frozen firmware fixtures remain available. Select
`MICA2=1` in hardware or `--mica2` / a `MICA-2*` profile in the tools for the new
semantics. Board defaults retain the 1.0 firmware configuration.

## Advantages over RISC-V

These are measured **loop-body bytes**, excluding setup and termination:

| Operation | MICA 2.0 | RV32IC | RV32IC + Zcb |
| --- | ---: | ---: | ---: |
| Decrement and branch | 2 | 4 | 4 |
| Counted byte-copy loop, F enabled | 6 | 16 | 12 |
| Counted word-copy loop, F enabled | 6 | 12 | 12 |
| One stack save and restore | 4 | 4 | 4 |

MICA executes the copy body in three instructions instead of six, combining
the pointer updates with the memory operations and decrement with the branch.
Both loops still perform one data load and one data store per element. MICA-2C
also exposes eight register slots, versus sixteen for RV32E and thirty-two for
RV32I. That reduces the architectural register budget; register pressure and
the physical register-file implementation determine the actual tradeoff.

Reproduce the byte counts with `python3 benchmarks/riscv_density.py` using LLVM's
`llvm-mc` and `llvm-objcopy`. The RISC-V programs are assembled and sized; this
benchmark does not execute a RISC-V processor. Full application size, cross-ISA
cycles, Fmax and energy per task need separate comparisons.

## Hardware and project status

The [2.0 verification report](docs/engineering/MICA2_VERIFICATION.md) records local
RTL simulation, retirement checks, component formal results and Yosys resource
mapping. [BUILDING.md](BUILDING.md) reproduces the checks. The earlier blanket
statement that RTL could not be simulated or synthesized is superseded by those
recorded runs.

Vivado placement/routing, timing closure, physical FPGA boot and rail-power
measurements remain pending. **No measured power or clock-speed advantage over
RISC-V is claimed.** A smaller loop is a demonstrated encoding advantage, not
a wattage or frequency measurement.

The SDK supports assembly development. A C/LLVM backend, pipelined execution,
protected tasks and multicore RTL remain open work. SIMD and atomics are chiefly
emulator capabilities. See [SDK status](SDK_STATUS.md) for support boundaries.

## Documentation

Start with the [documentation index](docs/README.md), then the
[2.0 scalar specification](docs/architecture/MICA2.md) and
[assembler guide](docs/toolchain/ASSEMBLER.md). The
[hardware drawing index](docs/hardware/DATAPATH.md) covers all current schematics.
The [1.0 compatibility reference](docs/architecture/ISA.md),
[historical r2 report](docs/engineering/IMPLEMENTATION_REPORT.md) and archived
measurements retain their original revision context.

MICA is released under the [MIT license](LICENSE).

# so what this all uh info compiles down to.
-------------------------
MICA (Microcontroller Instruction Core Architecture) is an independent 32/64-bit RISC architecture designed for microcontrollers, embedded systems, and low-power processors. Its goal is to challenge RISC-V in these areas by offering compact instructions, efficient execution, simpler hardware, and better performance per watt without unnecessary complexity. MICA aims to become a practical alternative for everything from small industrial controllers to more capable multicore embedded processors, with efficiency and flexibility at the center of its design.
