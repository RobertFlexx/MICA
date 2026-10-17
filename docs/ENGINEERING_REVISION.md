# MICA 1.0 engineering revision

This tree is a working SDK for a research ISA. It is not a finished CPU you can tape out. The new files focus on the boring parts that make processors useful: reproducible tooling, physical memory timing, testable specifications, and measurements that can survive someone else's laptop.

## One ISA, several implementations

MICA32 uses 32-bit scalar registers. MICA64 uses 64-bit scalar registers with the same 16-bit short encodings and optional 32-bit extended instructions. Eight architectural scalar registers are mandatory. Extension X adds eight more. F adds post-increment accesses and counted branches. B adds bit operations. M adds multiplication. A, V and T remain optional and have different implementation status in software and RTL.

No previously allocated v1.0 binary opcode was reassigned for this revision. The new software execution engines are alternate implementations of the same semantics, not new ISA features.

The C++23 assembler now supports `.assert expr[,message]`, `.error message`, `--map symbols.txt`, a bounded total expansion size, and direct detection of circular `.include` chains. Assembler expansion is still deterministic. There is no ELF writer, relocation engine, link editor or C compiler backend. Nobody should package this as a finished general-purpose compilation toolchain.

### Assembler audit checklist

- Lexer and expression parser handle common integer forms, symbols, unary and binary arithmetic, macros and include files. The code has negative tests and source/line diagnostics.
- The format is currently a flat byte image. `.text`, `.data`, `.rodata` and `.bss` are organization markers, not linkable sections.
- The symbol map is intentionally line based and sorted by address. A debugger can use it without reparsing a human assembly listing.
- The assembler rejects recursive includes and limits total expanded source to 200,000 lines. Macro expansions cannot silently eat unbounded memory.
- The test suite compares frozen binary fixtures so future edits cannot accidentally rename an instruction while rewriting its opcode.
- Still missing: independently specified ELF relocations, symbol visibility, separate compilation, fuzzing at scale, stable CLI error codes, portability and reproducible packaging tests.

## Execution engines and the 1,000 MIPS question

`mica-run` starts in its reference engine by default. `--fast` accelerates common 16-bit scalar instructions and F's `dbnz` without skipping checks for unsupported instructions. On anything outside its carefully limited set, it calls the reference interpreter. `--native-loops` adds a specialized native translation of exactly one loop shape:

```
loop:
    addi xD, K
    dbnz xC, loop
```

`xD` and `xC` must be distinct and writable, `xC` must be positive and small enough to finish inside the remaining step budget, and the engine must not be tracing or handling traps. This translator performs each iteration in native C++ and updates MICA's registers and retired count. It doesn't model wall-clock cycles. It isn't a whole-program JIT, nor does it optimize memory, atomics, SIMD, exception delivery, or unrelated instructions.

Measurements from the local AMD EPYC 9V74 host, in Release mode, with a 50 million iteration MICA loop, median of three runs:

| Mode | MICA32 | MICA64 |
| --- | ---: | ---: |
| Reference interpreter | 163.2 MIPS | 160.3 MIPS |
| Fast scalar engine | 263.2 MIPS | 260.5 MIPS |
| Native counted loop | 3,132.2 MIPS | 3,245.5 MIPS |

These are throughput measurements for this particular loop. The specialized translation result must **not** be used as a general emulator performance rating. Run `python3 benchmarks/emulator_mips.py --assembler build/mica-as --emulator build/mica-run` to reproduce the procedure on another host. The script validates returned registers and retired counts rather than timing a program that doesn't do anything.

### The next emulator step

A good next engine would predecode 32-bit envelopes and build basic blocks with explicit guards for traps, memory-mapped I/O and self-modifying code. A genuine native translator could then compile entire basic blocks, including loads/stores and bounded exits. Keep the reference model for differential testing. It's much better to be 300 MIPS and correct than 3,000 MIPS and quietly corrupt firmware.

## RTL: separate what works from what is merely wired on paper

The existing `mica_core.sv` has an asynchronous halfword fetch input, a zero-wait-state data interface, and an FSM with FETCH0, FETCH1, EXECUTE and HALTED. `mica_soc.sv` connects it to asynchronous-read RAM, UART TX and LEDs. This core was not rewritten into a ready/valid machine in this revision. Doing so without independent HDL simulation would be reckless.

The new `rtl/verilog/mica_sram.v` is a standalone synchronous SRAM primitive with 32/64-bit words, byte strobes, and a registered one-clock-later response. Read-during-write returns the old word, which is a documented choice, not a guess. It is useful when building a real memory subsystem but is **not drop-in compatible** with the existing zero-latency interface.

The new `rtl/vhdl/mica_watchdog.vhd` is an independent, windowed watchdog. Servicing it too soon asserts an early fault. Failing to service it within the programmed window asserts expiry. A malformed min/max configuration also expires. It uses `numeric_std` and explicitly sized unsigned counters, which makes the arithmetic readable and avoids accidental mixing of logic vectors with numbers. There is no watchdog-to-reset connection in the supplied SoC.

Why multiple HDLs? Plain Verilog-2005 makes the SRAM broadly accessible to older FPGA tools. VHDL-2008 is pleasant for strongly typed peripheral logic and parametrized state machines. SystemVerilog remains the main CPU RTL language because interfaces, enums, packed fields and assertions suit a processor. These are tooling and maintainability tradeoffs, not a claim that one language is inherently faster than another.

The hardware tests in CI use Icarus for the scalar core and standalone Verilog SRAM, GHDL for the watchdog, and Yosys for an independent SRAM synthesis check. This environment did not have those executables, so the new HDL paths are supplied with runnable tests but **not locally simulation-verified**.

## What could make MICA better for a controller?

The strongest direction is *total system energy to finish a real task*, not instructions per second alone. An attractive microcontroller would combine:

1. A genuinely small state machine for low-end control products, with the unused X, V, B, A and T hardware removed at synthesis rather than left toggling.
2. A compact base format with explicit F for pointer-heavy loops. Compare actual energy per byte of CRC, packet parsing, small actuator control and interrupt service. CORE-V and other processors already have related instructions, so this is an optimization question rather than a patent claim.
3. Different MICA32 and MICA64 physical datapaths even when machine code is similar. A 64-bit design should test independently gated upper arithmetic slices and show that enable logic costs less than the switching it saves.
4. A real SRAM wait-state interface and a flash fetch buffer. The memory path often dominates tiny embedded workloads, making a clever ALU irrelevant if every instruction stalls on flash.
5. Co-designed sleep and peripheral notification policy. A wakeup is expensive on a sleeping chip. Allow software to request bounded event batching with a strict latency limit, then prove it does not violate real-time deadlines.

All five are experiments until area, timing and power numbers exist. Don't claim a monopoly on clever hardware. Arm M-profile, CORE-V, Ibex and PicoRV32 are serious competitors.

## Fair comparison recipe

Build identical application workloads in MICA and a comparable RISC-V profile. Keep foundry/FPGA technology, target voltage, clock constraints, on-chip memory size, compiler optimization policy, and peripheral behavior as close as possible. Measure:

- Post place-and-route Fmax, with timing corner, slack, constraints and tool versions.
- LUTs/FFs/BRAM/DSP on the same FPGA, or standardized cell area, SRAM macros and leakage in ASIC synthesis.
- Joules per task including idle wakeups, not just dynamic watts while spinning in one arithmetic loop.
- Per-workload instruction counts and memory transactions, plus bytes of firmware and interrupts serviced per second.
- Worst-case interrupt latency and deadline misses under bus contention. Mean latency won't rescue a motor controller.
- 32-bit and 64-bit configurations separately, including the amount of code that actually needs 64-bit arithmetic.

Reference documentation:

- https://github.com/lowRISC/ibex/blob/master/doc/03_reference/pipeline_details.rst
- https://github.com/openhwfoundation/cv32e40p/blob/master/docs/source/instruction_set_extensions.rst
- https://github.com/YosysHQ/picorv32
- https://ghdl.github.io/ghdl/using/Synthesis.html

The details from these projects are guides to what good verification and realistic hardware design look like. Their cores, source files and binary encodings have not been copied into MICA.

## Release gate

Software passing is not the same as production readiness. Before v1.0 can be described as a release-quality physical core, require at least: an executable RTL simulator run, instruction-by-instruction differential checking against the C++ model, coherent memory error and trap semantics, consistent CSR read/write behavior, constrained synthesis with positive slack, FPGA hardware bring-up, a published test suite, and reproducible power data. Until then, call the hardware a prototype. It's a good word. It means the project has room to get good.
