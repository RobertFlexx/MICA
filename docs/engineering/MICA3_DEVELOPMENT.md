# MICA 3.0 development r1 engineering report

This revision starts MICA 3.0 development with an ISA 2.0-compatible scalar
implementation. It improves instruction selection, shared arithmetic hardware,
release metadata and engineering drawings. The
[architecture contract](../architecture/MICA3.md) defines the complexity budget
and retained binary interfaces. Earlier work and measurements remain in the
[2.0 r3 report](EMBEDDED_REFINEMENT.md).

## Audit findings and changes

The repository contains a multicycle scalar CPU, not a pipelined processor.
Vector and atomic instructions execute in software only. The C path lowers a
restricted Clang IR subset; it is not an upstream LLVM backend. Protection,
secure boot, hardware SIMD, division and high-half multiplication are absent.
These gaps remain explicit in the instruction matrix and numbered drawings.

The compiler unnecessarily requested long encodings for small constants,
destructive arithmetic, frame adjustments and logical shifts. It now selects
existing li, short scalar operations, addi, shli and shri when the register and
immediate fit. A zero displacement is omitted.
Conventional three-operand assembly selects a short form when the destination
equals the first source and both registers are low; otherwise it uses existing
ALU3. High-register mov uses add-with-zero. Explicit long mnemonics remain fixed.
Forward symbolic literal relaxation is still incomplete.

Short, ALU3 and word multiply previously synthesized through separate expression
paths. They now share one enabled product and common scalar read muxes. W32 zeros
the unused operand halves. MUL=0 removes the product. No opcode, architectural
register, memory transaction or controller state was added.

The machine-readable WFI, ldw and ecall descriptions incorrectly stated only their
legacy semantics. They now state both compatibility contracts. Runtime behavior
and encodings are unchanged. The generated 153-instruction engineering inventory
records fields, allocation envelopes, semantics, typical uses and latency limits.

The hardware CI run for d29511c completed its HDL checks but failed the compiled
density stage because llvm-objcopy was absent. CI now installs LLVM 18 explicitly;
the benchmark also accepts an explicit objcopy path and discovers its versioned
binary. Diagram checks match the current elaborated RTL. Source checksums cover
the 3.0 development tree.

## New hardware reference collection

The [20-sheet collection](../hardware/schematics/v3/README.md) is newly generated
from editable sheet definitions. It includes DOT, SVG, PDF and PNG for every
numbered view, independently elaborated C32/E32/L64 cores, actual SoC instance
connections and the constrained Arty A7 boundary. It is an RTL engineering
reference, not a board electrical schematic. Pipeline and security pages report
implementation gaps; unsupported blocks are not fabricated.

Validation checks names, widths, parameters, module instances, connection bits,
source hashes and preview hashes. The eight FPGA pins are checked against the
vendor's Arty A7 master constraints for Rev D/E. Negative tests reject missing
signals/modules and an incorrect XLEN64 PC width. Functional region arrows are
reviewed RTL descriptions, not a gate-level equivalence proof.

## Confirmed measurements

Matched Yosys xc7 mapping uses OSS CAD Suite 2026-10-17, 4 KiB SRAM and the same
profile/peripheral settings as the 2.0 r3 baseline. LUT totals sum LUT1..LUT6;
flip-flops sum the mapped FD cell types. These are mapping results, not routed
frequency, ASIC area or physical power.

| Configuration | r3 LUTs | r1 LUTs | r3 / r1 flip-flops | r3 / r1 DSP48 |
| --- | ---: | ---: | ---: | ---: |
| MICA-2C | 4,736 | 4,328 | 983 / 1,004 | 0 / 0 |
| MICA-2E | 7,304 | 6,989 | 1,767 / 1,767 | 6 / 3 |
| MICA-2L | 15,128 | 13,967 | 2,888 / 2,888 | 23 / 10 |
| MICA-2E + parity | 7,602 | 7,236 | 1,783 / 1,783 | 6 / 3 |
| MICA-2E + RX/CRC/watchdog | 7,954 | 7,609 | 2,183 / 2,183 | 6 / 3 |

The compact implementation trades 21 more flip-flops for 408 fewer LUTs.
The expanded 32/64-bit implementations reduce both LUTs and DSPs. No matched
Ibex/PicoRV32/Cortex-M hardware comparison or timing advantage is established.

Complete ROM for the same array/structure/call/recursion C source was 896 bytes
on MICA-2C and 920 on MICA-2E in the r3 archive. Short literals and destructive
arithmetic reduced it to 768 and 792. Short addi, shli and shri, with zero
displacements omitted, reduce it to 712 and 736. That last pair was reproduced
on Clang 21.1.8 together with RV32I 404, RV32IC/EC/IC+Zcb 300, Cortex-M0+ 208
and Cortex-M4 204. The r3 archive's compressed RISC-V size of 244 bytes came
from Clang 23.1.3 and is not the figure from this host. Frontends use -O0 and
explicit startup/flat ROM; allocation and backend optimization differ.
Competitor images are built, not executed. This is a compiler-size improvement
and a remaining loss against those backends, not an ISA ranking.

Hand-written F+2C bodies remain denser than the assembled RISC-V and Thumb
sequences in the [loop comparison](../research/RISCV_COMPARISON.md). A byte-copy
body is 6 bytes, against 12 for RV32IC+Zcb and for both measured Thumb sequences.
A counted branch is 2 bytes, against 4 for Thumb. Stack save/restore ties at 4.

## Reproduction and incomplete gates

Use scripts/verify.py --all --build-dir build/verify-v3 for the full local suite.
The density, instruction-mix, sensor, fault and synthesis scripts retain their
commands and machine-readable output under build/. Source and binary archives
use the 3.0 name while ELF ISA versions remain 1.0/2.0.

The following gates remain incomplete: optimizing compiler and full ABI/runtime,
independent ELF sections and ROM initialization, pipelined CPU, hardware A/V,
MPU/secure boot, whole-core formal proof, finite external-memory response bounds,
routed timing, physical board execution and physical energy. No new ISA-only
feature is described as complete. This revision does not complete the roadmap.
