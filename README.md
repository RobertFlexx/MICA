# MICA 1.0

MICA is an experimental 32/64-bit embedded ISA and processor SDK. Engineering
revision r2 adds a transactional multicycle CPU, synchronous FPGA SRAM, precise
machine traps, ELF image objects and linking, retirement comparison, firmware
and measured hardware experiments. The ISA version remains **1.0**.

Design work focuses on compact encoding, useful embedded operations and
controlling hardware activity. Comparable workload, area and power measurements
will determine where these choices provide an advantage.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
python3 scripts/build_firmware.py --tools build
build/mica-run build/firmware/linked.elf
```

The linked example starts the assembly runtime, clears BSS, computes CRC-32,
and prints `MICA linked CRC OK` through UART. The SDK contains no C compiler.

```asm
.arch mica32
li8 x1,21
add x1,x1
wfi
```

Save this as `hello.mica`, then run `build/mica-as hello.mica -o hello.bin` and
`build/mica-run hello.bin`. The result is `x1=0x2a`.

The seven C++23 tools are `mica-as`, `mica-ld`, `mica-dis`, `mica-run`,
`mica-objdump`, `mica-nm` and `mica-objcopy`. Use `--help` for their interfaces.
`mica-run --profile MICA-E` enables the 32-bit embedded extensions. `--debug`
opens the emulator debugger. The reference interpreter remains the default;
`--fast` and the specialized `--native-loops` engine are optional.

For hardware, [BUILDING](BUILDING.md) describes the installed dependencies and
commands. The [ISA manual](docs/architecture/ISA.md) is normative. Start with
[SDK_STATUS](SDK_STATUS.md), the [audit](docs/engineering/AUDIT.md) and the
[implementation report](docs/engineering/IMPLEMENTATION_REPORT.md) for evidence
and remaining work. The [FPGA guide](docs/hardware/FPGA_BUILD.md) covers the
Arty A7-100 target. [Current drawings](docs/hardware/DATAPATH.md) are generated
from and checked against RTL names. The [peripheral guide](docs/hardware/PERIPHERALS.md) covers the Verilog UART receiver/FIFO and VHDL CRC engine, including interrupt-driven echo firmware.

This revision does not provide a pipelined performance core, protected user
mode, coherent multicore, SIMD hardware, a general JIT, timing closure or a
physical board boot measurement. The single-mode timer scheduler is a working
context-switch demonstration. It is not an RTOS qualification.

Existing firmware fixtures remain byte-identical. MIT licensed.
