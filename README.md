# MICA 1.0
> *Microcontroller Instruction Core Architecture*

MICA is a small experimental 32/64-bit RISC architecture for embedded controllers. The project has its own binary encoding, a C++23 assembler and disassembler, a reference emulator, faster execution paths, freestanding assembly routines, and a SystemVerilog CPU prototype.

The ISA version is still **1.0**. This engineering update doesn't reassign any existing instruction encoding. The binaries in `examples/firmware` are frozen compatibility fixtures.

MICA explores a different approach to embedded processor design, focusing on compact instruction encoding, efficient execution, and reducing unnecessary hardware activity. The goal is to develop a practical architecture that can compete with established embedded cores in performance, power consumption, and implementation complexity. Hardware benchmarks and real-world workloads will determine where these design choices offer meaningful advantages.

## Build the tools

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
ctest --test-dir build --output-on-failure
```

C++23 and Python 3 are needed. GCC and Clang are supported on the development hosts. The reference emulator uses the `__int128` extension supplied by those compilers. The archived Linux binaries are only convenience builds, not portable binaries for every OS.

## Hello, MICA

```asm
.arch mica32
li8 x1, 10
li8 x2, 20
add x1, x2
wfi
```

```sh
build/mica-as example.mica -o example.bin --map example.map --listing example.lst
build/mica-dis example.bin
build/mica-run example.bin
```

The exit state includes `x1=0x1e`. A symbol map is useful when matching firmware addresses to source labels. `.assert 1` and `.error "bad build"` are now available for simple compile-time guards.

## Emulator engines

- Default: the reference interpreter. Use this for debugging and differential verification.
- `--fast`: a fast path for short scalar instructions and counted branches. Everything else falls back to the reference engine.
- `--native-loops`: a specialized native counted-loop translator on top of `--fast`. It recognizes an `addi` plus backward `dbnz` loop, not arbitrary MICA code.

The local microbenchmark reaches more than 3,000 million **emulated** instructions per second on the translated loop only. General fast interpretation measured around 260 MIPS for the same loop. Don't quote the specialized figure as overall emulator performance.

```sh
build/mica-as --flow benchmarks/throughput32.mica -o bench.bin
build/mica-run --flow --fast bench.bin --steps 22000000
build/mica-run --flow --native-loops bench.bin --steps 22000000
python3 benchmarks/emulator_mips.py --assembler build/mica-as --emulator build/mica-run
```

The benchmark checks the machine's output and includes setup instructions in its retirement count. Host frequency, CPU load and compiler options matter.

## HDL languages and why they're separate

- `rtl/mica_core.sv`: existing multicycle CPU, 32/64-bit scalar subset. This is still SystemVerilog.
- `rtl/verilog/mica_sram.v`: plain Verilog synchronous SRAM with byte writes, made for broadly supported FPGA inference.
- `rtl/vhdl/mica_watchdog.vhd`: VHDL-2008 typed windowed watchdog, with sticky early/expired faults.
- `rtl/mica_soc.sv`: existing demonstration SoC with **asynchronous RAM reads**, UART and GPIO.

The Verilog SRAM is not wired to the SoC. It cannot be until the processor supports wait states and registered memory responses. The watchdog is also standalone. Their testbenches and CI hooks are in the tree, but no HDL simulator was installed in the local environment used for this update.

For hardware work, start with the [board guide](docs/HARDWARE.md), [language modules](docs/HDL_BUILD.md), and [signal diagrams](docs/SCHEMATICS.md). Don't connect a motor driver straight to FPGA pins. The smoke will have opinions.

## What to read

| Topic | Reference |
| --- | --- |
| Exact instructions | [ISA](docs/ISA.md), [extensions](docs/EXTENSIONS.md) |
| Assembly and API | [Dialect](docs/DIALECT.md), [ABI](docs/ABI.md), [runtime](docs/RUNTIME.md) |
| Engineering changes | [Revision log](docs/ENGINEERING_REVISION.md), [status](SDK_STATUS.md) |
| Physical implementation | [RTL build](docs/HDL_BUILD.md), [schematics](docs/SCHEMATICS.md) |
| Research priorities | [Architecture research](docs/ARCHITECTURE_RESEARCH.md) |
| Test plan | [Verification](docs/VERIFICATION.md) |

## What isn't ready

No finished compiler, ELF linker, ISO C/C++ standard library, protected user mode, coherent multicore, 128-bit SIMD hardware, complete atomics in RTL, verified synchronous-memory system, timing closure or measured energy advantage. The assembler is a serious prototype, not a qualified production toolchain. Those missing pieces matter more than the release number.

Licensed under MIT. Existing source and binary formats remain at MICA 1.0.
