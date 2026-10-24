# MICA 3.0 development r1 release notes

This development revision retains ISA 2.0 and explicit 1.0 compatibility. The
SDK and archive version advance to 3.0; ELF ISA flags, machine encodings and
existing command defaults do not change. Select a profile or --mica2 explicitly.

The compiler selects existing shorter forms, including fitting addi and logical
shift immediates. The scalar core shares optional
multiply hardware, and the new 20-sheet collection is checked against elaborated
RTL and verified FPGA constraints. The [development report](docs/engineering/MICA3_DEVELOPMENT.md)
publishes resource/code-size measurements and remaining validation gaps.

This is the start of 3.0 development. Pipeline, hardware A/V, full compiler and
runtime, isolation, physical timing/power and board validation remain incomplete.

## Historical MICA 2.0 notes

MICA 2.0 adds compact stack accesses, a two-byte counted branch, PC-relative
address arithmetic, wakeable WFI and explicit STOP to the preserved 1.0 SDK.

## Current revision

- Fix CI on runners without ripgrep; source discovery and archive checks also
  work without Git. Add extracted-source CI and installed 2.0 release tests.
- Add `PCREL6` for separately assembled compact counted loops and retain object
  alignment through linking, including at nonzero origins.
- Reject literal overflow before shortening `li32`; make trap TVAL independent
  of tracing and make ELF disassembly respect revision and extension metadata.
- Define ordered compiler, RTL, FPGA and measurement milestones in the roadmap.

## Earlier 2.0 revisions

- Repair MICA 2.0 ELF feature parsing, linking and runtime revision checks, and
  reject objects with incompatible ISA semantics.
- Add `ADRPC16` relocation support for existing PC-relative instructions,
  including cross-object symbol references in MICA-32 and MICA-64.
- Harden PC-relative displacement arithmetic, signed relocation addends,
  operand parsing and source formatting against partial edits.
- Add published 32/64-bit ELF firmware examples, regression suites and an
  updated emulator/ELF workflow diagram. No RTL instruction encoding changes.

- Execute 2C operations in the assembler, disassembler, emulator and transactional
  RTL at XLEN32/64; retain all 14 frozen 1.0 firmware fixtures.
- Verify all three 2.0 profiles with retirement traces under randomized bus stalls,
  precise faults and reset replays; add timer wake/STOP SoC tests at both widths.
- Fix masked-IRQ WFI wake and XLEN32 stack-address wrapping in the emulator,
  and remove 64-bit decode width warnings.
- Map all three 2.0 and four legacy SoC configurations through Yosys xc7 synthesis.
- Refresh every existing schematic path, all previews and source/preview hashes.
- Restore the omitted Vivado script and add an explicit 2.0 image option.
- Preserve the 1.0 documentation layout, update current guides, archive 2.0
  evidence separately and add a reproducible RISC-V density comparison.

The MICA F+2C byte-copy body is six bytes versus sixteen for RV32IC and twelve
for RV32IC + Zcb. Stack save/restore ties compressed RISC-V. See the
[comparison](docs/research/RISCV_COMPARISON.md) for exact scope.

Physical FPGA boot, routed timing, measured power and clock-speed advantages
remain pending. Compiler, MPU, pipelined/multicore RTL and vector hardware remain
future work. See [SDK status](SDK_STATUS.md) and the
[verification report](docs/engineering/MICA2_VERIFICATION.md).
