# Experimental MICA ELF image objects

The implemented format is little-endian **ELF64**, including for MICA32, with
experimental e_machine=0xff4d. This number is not officially assigned to MICA.
ET_REL objects and ET_EXEC images use the same constrained section layout: null,
`.mica.image` (PROGBITS/WAX, alignment 16), `.rela.mica.image` (RELA), `.symtab`
(24-byte entries), `.strtab`, `.shstrtab`. e_flags bit 0 selects XLEN64; bits 8..15
record required X/M/F/A/V/B/T/PERF features. Bit 16 records the MICA 2.0
semantic revision. Bits 1..7 and 17..31 must be zero. A 2.0 object cannot be
linked with a 1.0 object because some instructions have changed behavior.
The emulator requires explicit `--mica2` (or a matching profile) to execute
2.0 ELF, and rejects loading 1.0 ELF in 2.0 mode. This prevents silently
interpreting an old program under revised instruction semantics. It also rejects
executables requesting extensions disabled in the selected runtime profile.
`mica-objdump` prints the recorded ISA revision and required extensions. No program headers are emitted; the
MICA loader explicitly loads the allocated image section and entry. This is a
documented SDK-specific ELF subset, not a generic Unix executable ABI.

Text/data/rodata/bss directives remain organization markers in one image section.
BSS bytes are materialized; the startup example also clears its explicit BSS range.
Separate independently placed sections, NOBITS, debug info, dynamic linking and
archives are not implemented. Symbols use local/global/weak binding, undefined
section 0, image section 1 or absolute SHN_ABS. The linker honors strong over weak
definitions, rejects duplicate strong definitions, and resolves an undefined weak
reference to zero. Local names remain scoped to their object.

| Relocation | ID | Field |
| --- | ---: | --- |
| ABS32,ABS64 | 1, 2 | little-endian data word, exact unsigned width |
| LI32,LI64 | 3, 4 | complete8/24-byte pseudo expansion, template checked |
| PCREL8,PCREL11 | 5, 6 | short conditional/unconditional halfword displacement |
| PCREL14,PCREL20,PCREL24 | 7, 8, 9 | long comparison/counted/jump displacement |
| ADRPC16 | 10 | long WIDE/ADRPC immediate; signed PC-relative halfwords from instruction PC |

RELA addends are signed 64-bit. Absolute result is S+A; relative displacement is
`(S+A-(P+instruction_length))/2`, where P is the patched instruction address.
`ADRPC16` is `(S+A-P)/2` instead, because `adrpc` uses the instruction's PC.
Offsets must be even and fit the signed field. LI relocations replace all 16-bit
pieces while retaining register/opcode fields and verifying the shift instructions
in LI64. Values too large for LI32/ABS32 are rejected. No other relocation IDs are
advertised or accepted.

Assembly relocation expressions are a symbol optionally plus/minus an absolute
constant, in li32/li64, `adrpc`, supported branches and .word/.quad. Local references are
relocated too. Complex symbolic arithmetic and symbolic memory displacement are
rejected; use an explicit address load. Output is deterministic and has no build
timestamp. Reader limits include 64 MiB files/combined link inputs, 32 MiB images,
bounded section counts, string sizes, symbols, relocations and checked offsets.
Malformed input tests and the libFuzzer target exercise the reader.
