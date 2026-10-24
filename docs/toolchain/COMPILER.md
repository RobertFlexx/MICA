# Experimental C compilation

`mica-cc` runs Clang's freestanding RISC-V32 frontend to obtain little-endian
32-bit LLVM IR, then lowers a restricted unoptimized subset to MICA assembly.
Clang does not emit MICA machine code. This is a working translation path, not
an upstream LLVM target backend or a complete C implementation.

Supported targets are MICA-2C and MICA-2E. The data model has 8-bit char, 16-bit
short, and 32-bit int, long and pointers. Scalar arguments use x1..x4; x1 returns
a scalar. Frames grow down and are aligned to 16 bytes at calls. x5 and x6 are
saved in every frame. x12..x15 remain callee saved. Structure and array layout
uses explicit alignment and tail padding. Globals are materialized in SRAM image
objects. Independent ROM/data/BSS sections and startup copying remain open.

The implementation supports integer arithmetic, signed/unsigned comparisons,
shifts, pointer arithmetic, scalar loads/stores, volatile accesses, globals,
arrays, local structures, branches, loops, direct calls and recursion. Four scalar
arguments are the limit. MICA-2C uses a shift/add multiply sequence; MICA-2E uses M.
Short stack forms are selected where legal. MICA-2E allocates local SSA values to
x8..x11 when all uses remain within one basic block and no call can clobber them.
Other values have stack homes. This is a small allocator with substantial remaining
spill traffic; it is not a competitive optimizing compiler.

MICA 3.0 development selects existing short destructive arithmetic and known
small literals. Frame adjustments use addi when the signed displacement fits in
eight bits; logical shifts use shli and shri when the register is low and the
amount is below 32. A zero displacement is not emitted. This changes code size
without allocating opcodes or changing the ABI. The
[development report](../engineering/MICA3_DEVELOPMENT.md) compares the resulting
complete ROM with the previous compiler and other targets.

Unsupported IR fails with a function/instruction diagnostic before replacing an
existing output. This includes floating point, 64-bit integers, division,
aggregate arguments/returns, varargs, internal linkage, dynamic allocation,
PHI/select/switch, atomics, inline assembly, memory intrinsics and C++ features.
Many legal C programs therefore remain unsupported. Local array initializers can
introduce an unsupported memcpy intrinsic; explicit element assignments work.

Build the source SDK, then run:

```sh
python3 compiler/mica_cc.py compiler/tests/program.c -o build/program.o
python3 compiler/tests/run.py --tools build
python3 scripts/build_sensor_demo.py --tools build
python3 scripts/test_sensor_demo.py --tools build
```

The last command needs Icarus and GHDL. The first three need Clang and the SDK.
`-S` emits assembly; `--clang` and `--assembler` select tools explicitly.
Installed SDKs provide `mica-cc` and its lowering module alongside the assembler.
`firmware/sensor/Makefile` builds the installed C and startup examples using these
tools. The [sensor demonstration](../hardware/DEMONSTRATORS.md) documents devices
and execution assumptions.

Tests compile separate translation units, recursion, local/global memory,
structures, signed narrow conversions, four arguments and deterministic random
integer loops. Native C supplies an independent result oracle. Emulator modes
and RTL retirement must agree, including preserved registers and SP. Code-size
comparisons report complete ROM bytes; current MICA output is substantially larger
than the tested RISC-V and Thumb output. See the
[engineering report](../engineering/EMBEDDED_REFINEMENT.md).
