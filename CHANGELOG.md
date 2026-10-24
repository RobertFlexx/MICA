# Change log

## MICA 3.0 development r1

Start the 3.0 SDK development line while retaining ISA 2.0 encodings, ELF flags,
profiles and the explicit 1.0 compatibility contract. Centralize release metadata
for tool versions, installation and archives. No mandatory instruction is added.

Select existing short literals, destructive scalar operations, fitting addi/shli/shri
forms, and omit zero displacements in C output.
Accept concise three-operand scalar assembly and high-register moves through
existing encodings; preserve explicit long forms. Share the optional multiplier
and operand read muxes, isolate inactive inputs and zero W32 upper operands.
Correct the machine-readable legacy-only WFI/ldw/ecall descriptions.

Create a new 20-sheet hardware collection with editable DOT, SVG, PDF and PNG,
elaborated port/width/connection checks, vendor-checked FPGA pins and negative
width tests. Add a complete instruction engineering inventory, actual compiler
retirement counts and independent multiply-oracle regression. Repair LLVM
discovery in hardware CI. See the [development report](docs/engineering/MICA3_DEVELOPMENT.md)
for measurements and incomplete gates.

## MICA 2.0

### Development r3, 2026-10-23

Restore narrow C regressions and support constant GEP/MMIO pointer expressions.
Select compact stack accesses and allocate local MICA-2E values to x8..x11.
Add compiled timer/sensor/CRC/UART/watchdog firmware, native and RTL checks,
complete-program code-size comparisons and explicit compiler limits.

Add optional register parity with fail-stop detection and targeted injection.
Enter enabled interrupts directly from SLEEP and record entry/retirement latency.
Keep MICA-2D/2R/2S proposed. Regenerate drawings and restore strict checksum and
schematic CI checks. No new instruction encoding in this revision.

### Development r2, 2026-10-18

Add optional `ldpi.sb/sh/sw` in reserved long F slots, preserving existing bytes.
Validate encoding overlap and feature/version dependencies; execute the per-
instruction matrix. Reuse aligned long parcels and retain fetch words across
nonoverlapping stores/redirects. Add portable Verilog UART TX/SPI, VHDL event
counting, precise watchdog windows and optional MMIO integration.

Fix the formatter dependency that broke Linux/macOS CI. Add extracted-source
release validation and installed MICA 2.0 smoke tests. Add `PCREL6` compact
branch relocations, preserve ELF object alignment, reject overflowing literals
before relaxation, and correct trace-dependent trap values and ELF disassembly.
Expand the roadmap into ordered milestones with explicit completion gates.

Repair the 2.0 ELF feature flag mismatch, require compatible revisions when
linking or loading, report ISA requirements in `mica-objdump`, and implement
`ADRPC16` relocations for cross-object PC-relative addresses. Harden signed
relocation addends, branch displacement arithmetic and operand parsing. Add
32/64-bit firmware integration tests and transactional source formatting.
No machine instruction encoding was altered.

Add compact full-width stack accesses, short counted branches, ADRPC, wakeable
WFI, explicit STOP, signed XLEN64 word loads and 8/16-register profiles.
Preserve the 1.0 decode and all frozen firmware fixtures. Verify the new RTL
with Icarus, Verilator retirement comparison and Yosys mapping; fix masked
wake, XLEN32 stack wrapping and 64-bit decode width expressions.

Refresh all documentation and schematic paths, restore the omitted Vivado
script, add reproducible RISC-V density measurements, archive current evidence
separately and format SDK sources. Physical timing and power remain unmeasured.

## MICA 1.0, engineering r2

Transactional multicycle SystemVerilog core, precise fault commit, aligned-word
fetch reuse, synchronous dual-port Verilog SRAM, consistent CSR permissions,
timer interrupts, machine context-switch demonstration, retirement interface
and randomized Verilator comparison. The old core interface is an adapter.

Added C++ ELF image objects, nine supported relocation types, linking, symbol
inspection, executable loading and firmware conversion. Hardened expression
nesting, file sizes, ELF arithmetic, reservations and vector range checking.
Added profiles, source conditionals, binary inclusion, lossless disassembly,
CLI debugging, startup, FIR and linked CRC examples, proofs and synthesis flows.

Existing instruction encodings and frozen firmware bytes are unchanged.
Reserved opcode aliasing, illegal-instruction side effects, permissive reserved
CSRs and mixed-width reservation success are corrected behavior.

Added native VHDL CRC-32/ISO-HDLC with independent numerical tests, a
transactional SystemVerilog CRC adapter, and portable Verilog-2005 UART receive
and FIFO logic. Both XLEN SoCs execute CRC/RX interrupt/serial echo firmware.
Arty RX uses the vendor's A9 pin and the Vivado project reads native VHDL.

The guides now have a documentation index, topic-specific navigation and
updated Linux/macOS CI results.

## MICA 1.0, engineering r1

Historical software baseline: flat assembler/disassembler, reference and short
fast interpreters, specialized counted-loop translation, asynchronous-memory
prototype RTL, assembly libraries and initial independent HDL modules.
