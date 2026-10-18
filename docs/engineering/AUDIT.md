# MICA 1.0 engineering audit

Baseline: commit `7accf98a162fabb03ae1afcf8cf0f2e95ea9fb5a`, 2026-10-17. ISA version
remains 1.0. Engineering revisions do not reassign instructions.

## Baseline inspection and execution

Inspected `toolchain`, `sim`, `rtl` (SystemVerilog, Verilog, VHDL), `stdlib`,
`include`, `tests`, `examples`, `benchmarks`, `boards`, `schematics`, CMake, GitHub
Actions and the architectural documentation. The initial working tree was clean. GCC
15.2.1 Release built all three tools. All three original CTest targets passed
(integration, ten frozen binary fixtures, fast differential). The integration suite
conditionally skips a comparison to an unavailable old SDK. Compiler diagnostics
include GNU `__int128` extension warnings and a disassembler precedence warning. See
`baseline-software.txt` for raw results.

Initially installed: CMake, Ninja, GCC, Clang, Python, Graphviz. No HDL simulator,
Yosys, SBY or Vivado was on PATH. HDL tools must be obtained and the baseline tested
before hardware results are claimed. The obtained Icarus compiler built the original
sim32 test, but its execution timed out after90 seconds. r2 replaces that core
logic; all corresponding revised smoke tests now complete. See baseline-hdl.txt.

## Findings

Severity: critical = incorrect architectural results or host memory safety; high =
reproducible incorrect behavior; medium = incomplete contract/tooling. The
implementation report records which findings have been corrected.

| ID / category | Severity | Cause and affected components | Correction | Validation |
| --- | --- | --- | --- | --- |
| A01 Architectural correctness | high | Emulator increments PC before faults, throws host exceptions instead of precise architectural traps; odd jumps can write LR before failure. `sim/emulator.cpp` | Prevalidate encodings, stage state, retain faulting PC, define trap causes and commit boundary | Illegal/reserved, fault and jump tests plus retirement differential |
| A02 Architectural correctness | high | CSR reads/writes accept reserved IDs in emulator, differ from RTL; timer storage never ticks; hardware cycle reads return zero | Shared CSR map, explicit permissions/masks, real counters and timer comparison | Invalid accesses, counter monotonicity, timer interrupt and return tests |
| R01 RTL correctness | critical | Short op8 assigned to six-bit `operation`; opcodes 64..255 alias real instructions. `rtl/mica_core.sv` | Preserve all eight opcode bits, reject reserved values | Exhaustive short-encoding legality regression |
| R02 RTL correctness | critical | Nonblocking register writes remain scheduled when `illegal` or odd `nextpc` is detected | Decode into pending writes; commit only on successful instruction completion | Invalid unary/shift/jalr must preserve state |
| R03 RTL correctness | high | Fetch and LSU assume combinational reads, no response ownership or bus error handling. SoC uses asynchronous byte RAM | Transactional core and synchronous byte-write SRAM adapter, single outstanding request, explicit faults/reset | Random acceptance stalls, response latency, errors, reset and firmware |
| R04 RTL correctness | high | Address scaling mixes signed/unsigned operands; core and SoC stack reset alignment differ for unusual RAM sizes | Explicit signed extension before scaling, common aligned stack reset | Negative offsets and nonstandard memory size tests |
| T01 Toolchain | high | Disassembler ignores reserved bits in many formats, emits valid instructions for illegal bytes; output can lose encoding information | Shared encoding validator, lossless `.half`/`.byte` fallback, assembly output mode | All 65,536 short words and randomized long words round-trip |
| T02 Toolchain | medium | Flat images only; section markers are cosmetic; no separate compilation, relocations or linker | Defined bounded ELF relocatable subset and linker, reject unsupported relocation expressions | Multi-file firmware, overflow/undefined/duplicate symbols, malformed ELF |
| S01 Security and memory safety | high | Recursive expression parser has no depth bound; line length and file reads unbounded before checks | Bound expression depth, source/file sizes and output allocation | Deep expressions, huge source and corrupt input tests under sanitizers |
| S02 Security and memory safety | high | Atomic SC does not compare reservation width; destination validation can follow a store; vector accesses can partially update before range faults | Validate all operands and full RAM range before effects; width-qualified reservation | Mixed-width LR/SC, disabled registers, boundary vector tests |
| P01 Performance | medium | Two-halfword fetch repeats memory work; no memory-transaction counters | Optional aligned-word fetch reuse with redirect and fence invalidation | Cached/uncached traces and measured fetch transactions |
| P02 Performance | medium | No synthesized area/timing/activity evidence for ALU research or hardware comparisons | Conventional and segmented equivalent ALU experiments, archive actual tool output | Random equivalence, synthesis and VCD activity; no energy claims |
| M01 Missing functionality | medium | No pipelined core, general JIT, compiler backend, user protection, coherent multicore or SIMD RTL | Keep these out of verified hardware profiles; track explicit acceptance gates | Status matrix tied to executable tests |
| D01 Documentation/usability | high | ISA directs reader to code; RTL and software exceptions/MMIO differ; benchmarks search obsolete `cycles=` output | Normative specification and generated encoding tables; correct benchmark parser | Generated-file check, examples, measured report |
| V01 Verification gaps | high | RTL never simulated locally; tests include source regex instead of behavior; no retirement comparison | Executable RTL harness with deterministic random memory and architectural events | Verilator differential, Icarus/GHDL components, CI |
| V02 Verification gaps | medium | No formal properties or malformed object corpus; workflow availability unverified | Narrow proofs with documented assumptions, bounded fuzz/sanitizer paths | Proof logs and honest timeout/missing-tool reporting |

## Compatibility policy

`examples/firmware/*.bin` are retained unchanged. Their SHA-256 values and expected
behavior are recorded in the compatibility ledger. Corrections to reserved
encodings, invalid CSR accesses, overflowing address calculations and fault side
effects are deliberate tightening of erroneous or undefined behavior. Existing
nonfaulting supported programs keep their encodings and results. The historical T
`ecall` convention (EPC = next PC) is retained.

## Dependency order

1. Preserve baseline evidence and fixtures; correct unsafe decode and parsing.
2. Share encoding/profile/CSR descriptions and establish a normative contract.
3. Implement precise reference behavior and a comparable retirement stream.
4. Implement transactional multicycle RTL and differential verification.
5. Integrate synchronous SRAM and firmware/peripherals; verify HDL languages.
6. Add real object/link tools and reproducible examples.
7. Measure bounded research experiments and complete release documentation.

Later performance pipelines, protected multitasking, multicore and vector hardware
require their own implementation and validation milestones.

## Disposition in r2

A01/A02/R01..R04/T01/S01/S02 are corrected for the advertised scalar reference
scope, with regression tests. T01 also included a left-justified hexadecimal
byte-comment display defect, now checked. T02 has a working constrained ELF
image-object/linker implementation; independent sections and a mature parser remain
open. P01/P02 have actual implementations and measurements. M01 remains explicitly
incomplete. D01 and V01/V02 now have normative references, executable
HDL/differential/formal paths and recorded evidence. Remaining coverage and physical
validation limits appear in the implementation report.
