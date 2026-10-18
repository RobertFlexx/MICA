# MICA 2.0 scalar architecture delta

This document is normative for the `2C` profile. Read it together with the
[MICA 1.0 scalar specification](ISA.md). Anything not overridden here keeps its
1.0 meaning. Select the 2.0 decode in the C++ tools with `--mica2` or one of
the `MICA-2*` profiles, and on the RTL core with parameter `MICA2=1`. Without
that selection, all new encodings are illegal. All short instructions remain 16
bits and all long instructions remain 32 bits. The short-class length bits did
not move.

## Register budget

`MICA-2C` has eight physical scalar registers, including zero, link and stack.
`MICA-2E` and `MICA-2L` have sixteen. Three-bit operands in short instructions
address x0..x7 in all profiles.

| Profile | XLEN | Registers | Scalar options | Hardware status |
| --- | ---: | ---: | --- | --- |
| MICA-2C | 32 | 8 | 2C | RTL simulation, retirement comparison, Yosys mapping |
| MICA-2E | 32 | 16 | X, M, F, B, T, 2C | RTL simulation, retirement comparison, Yosys mapping |
| MICA-2L | 64 | 16 | X, M, F, B, T, 2C | RTL simulation, retirement comparison, Yosys mapping |

## New 16-bit R allocations

All entries use the original R halfword: `00 | op8[7:0] | d[2:0] | s[2:0]`.

| `op8` | Assembly | Exact effects |
| --- | --- | --- |
| 31 | `ldsp d,[sp+offset]` | `addr = old(x7) + offset`; read XLEN bits; update d on successful response |
| 32 | `stsp d,[sp+offset]` | `addr = old(x7) + offset`; store low XLEN bits of old(d); no SP change |
| 33..40 | `dbnz.s d,target` | `tmp = (old(d)-1) mod 2^XLEN`; write d; branch on tmp != 0 |
| 41 | `stop` | Enter STOP, remain stopped until reset; debug and test exit, not a sleep instruction |

For `ldsp` and `stsp`, `s` is a **three-bit unsigned slot index**, not a
register number. `offset = s * XLEN/8`. Valid offsets are 0..28 on XLEN32,
and 0..56 on XLEN64. The base is always x7. `ldsp x0` must still perform the
read and can fault. Writeback is never issued on a load error. Failed stores
must not modify memory. A precise trap leaves all affected register state
unchanged. Neither form implicitly increments SP. When `ldsp` names x7 as its
destination, its successful load replaces SP using the address calculated from
the old SP. `stsp x7` stores the old SP without changing it.

For `dbnz.s`, `d` cannot be x0. The signed six-bit halfword offset is encoded
as `(op8-33)<<3 | s`; it is sign-extended and scaled by two. Branches are
relative to `PC+2`. The inclusive reach is **-64 to +62 bytes** relative to
`PC+2`. Branch destination validation and wrap rules follow the 1.0
specification. The decrement happens even when the branch is not taken. This
instruction requires no separate count register or loop controller.
In ELF objects, `dbnz.s d,symbol[+/-addend]` uses `PCREL6` (relocation ID 11).
The linker patches the split displacement while preserving `d`, checks the
instruction template and rejects an unaligned or out-of-range target. Local
labels use the same relocation as external symbols. Linking never silently
widens this two-byte instruction; use `dbnz` with F for longer reach.

## New PC-relative address instruction

`adrpc d,imm16` uses the existing extended WIDE major (2), subopcode 3, and
16-bit signed displacement field. It writes

```
d = (instruction_PC + 2 * sign_extend(imm16)) mod 2^XLEN
```

The assembler argument is a **halfword displacement**, not a byte displacement.
`adrpc x3,2` at address zero writes 4. It does not dereference memory.
`adrpc` supports the `ADRPC16` ELF relocation for `adrpc d,symbol[+/-addend]`
in relocatable assembly objects. It computes the signed halfword displacement
relative to the **instruction PC**, not the next instruction. The linker rejects
unaligned or out-of-range targets. This supports references to nearby literals
and symbols.

## Full-width and word behavior

MICA-2L interprets the short `ldw` as **sign-extending** on XLEN64, following
the existing sign-extended 32-bit arithmetic result convention. The existing
`ldwu` instruction remains the explicit zero-extending load. This semantic
change is selected only in 2.0 mode. Existing MICA 1.0 images run with the
old semantics when MICA2 is disabled. `ldsp` on XLEN64 reads all 64 bits.

The separate 32-bit W arithmetic instructions retain their sign-extended result.
Flow loads retain their 1.0 zero-extension semantics.

## Sleep and trap changes

In MICA 2.0, `wfi` retires and enters SLEEP. It does not fetch or retire more
instructions until a wake signal arrives. The minimal core can wake using an
external `irq_i`, without requiring the T trap extension. When T is enabled,
software/external/timer pending bits can wake the core and delivery follows
the existing interrupt enable and mask rules. Pending alone wakes, while
handler entry requires the appropriate enable bits.

For 2.0 software exception `ecall`, EPC is the **address of ecall**, not the
next PC. A handler must advance EPC explicitly when it wants to skip the
faulting instruction. This differs from 1.0 and matches other synchronous
fault behavior. No instruction may partially retire as a consequence of a
fault or an interrupt. T supports one active handler. Exception priorities,
automatic stacking, nested handlers and memory protection are not implemented.
Use `wfi` for an idle loop; `stop` terminates execution until reset.

## Implementation provenance

- Machine-readable 1.0 encoding snapshot: `isa/encodings/mica1.json`
- 2.0 allocation: `isa/encodings/mica2.json`
- Compact-2 opcode contract: `isa/encodings/mica2-compact.json`
- C++23 encoder: `toolchain/assembler.cpp`
- Emulator: `sim/emulator.cpp`
- SystemVerilog: `rtl/mica_core_txn.sv`
- Tests: `tests/mica2.py`, `rtl/tb_mica2.sv`

The [2.0 verification report](../engineering/MICA2_VERIFICATION.md) records
executed HDL simulation, retirement comparisons, reset/fault/wake tests and
mapped synthesis. Physical board validation, routed timing and power remain
pending. The [RISC-V comparison](../research/RISCV_COMPARISON.md) measures the
compact loop encoding advantage separately from physical performance.
