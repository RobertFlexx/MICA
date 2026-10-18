# Change log

## MICA 2.0

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
