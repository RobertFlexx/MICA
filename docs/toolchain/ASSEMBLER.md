# Assembler

`mica-as` is a C++23 two-pass assembler. It writes raw binary by default and ELF
image objects with `-c`. The [linker guide](LINKER.md) shows separate compilation;
the [dialect reference](DIALECT.md) covers source syntax.

## Options and output

`--xlen`, `--profile`, `--xreg`, `--mul`, `--flow`, `--bitops`, `--atomic`, `--simd`
and `--trap` select the target features. `--mica2` enables 2.0, as do the
`MICA-2C`, `MICA-2E` and `MICA-2L` profiles. See the
[2.0 instruction guide](../architecture/MICA2.md). Options are processed in order, so an
option after `--profile` can override part of that configuration.

| Option | Output |
| --- | --- |
| `-o PATH` | Binary image, or ELF object with `-c` |
| `--map PATH` | Stable address/name map |
| `--listing PATH` | Encoded bytes with source file and line |
| `--hex PATH` | Intel HEX for a flat image |

Intel HEX has record syntax; SRAM initialization uses the separate word-file
converter. See the [memory guide](../hardware/MEMORY_INTERFACE.md).

The assembler supports labels, constants, expressions, macros, includes, repeats,
conditionals, data directives, aliases and pseudoinstructions. Encoding diagnostics
identify the file, line and source text. Column spans, machine-readable diagnostics,
branch relaxation and an optimizer remain open frontend work.

## Input limits

| Resource | Limit |
| --- | ---: |
| Input source | 8 MiB |
| Line | 65,536 characters |
| Expression | 16,384 characters; 128 recursive levels |
| Processed expansion | 200,000 lines; 32 MiB |
| Include-read depth | 12 |
| Expansion depth | 24 |

Circular includes and excessive recursion fail with diagnostics. Expressions use
wrapping unsigned 64-bit arithmetic, with checked literal conversion, shift counts
and division by zero. Encoded immediates and branches still have to fit their
instruction fields.

`.set` redefinition uses final two-pass symbol values. `.const` and `.equ` are
better suited to immutable values. Object relocation expressions accept a smaller
set of symbolic forms than flat-image expressions; the [object-format
reference](OBJECT_FORMAT.md) lists those forms.
