# MICA 2.0 release notes

MICA 2.0 adds compact stack accesses, a two-byte counted branch, PC-relative
address arithmetic, wakeable WFI and explicit STOP to the preserved 1.0 SDK.

## Current revision

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
