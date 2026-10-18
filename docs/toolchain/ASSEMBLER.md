# Assembler

`mica-as` is a dependency-free C++23 two-pass assembler. Raw binary is the
default; `-c` writes ELF image objects. `--xlen`, `--profile`, `--xreg`, `--mul`,
`--flow`, `--bitops`, `--atomic`, `--simd` and `--trap` select features. Flags are
processed in order, so flags after a profile can override it. `--map` writes a
stable address/name map, `--listing` writes bytes with source file/line, and
`--hex` writes Intel HEX for a flat image. HEX is not a readmemh file.

The parser supports labels, constants, expressions, macros, includes, repeats,
conditional blocks, data/alignment/reserve directives, aliases and explicit
pseudos. See DIALECT.md. Most encoding errors identify file/line/source text.
Column spans, machine-readable diagnostics, independent lexing/parser phases,
branch relaxation and a general optimizer remain unfinished. This is a working
assembler, not a production-qualified compiler frontend.

Limits:8MiB input source,65536 characters per line,16384 characters per
expression,128 recursive expression levels,200000 processed expansion lines,
32MiB processed source,12 include-read depth and 24 expansion depth. Circular
includes and recursion beyond these limits fail. Expressions use wrapping
unsigned64 arithmetic, with checked literal conversion, shifts and division by
zero. Emitted instruction immediates and branches must fit their specified
range. .set redefinition uses final two-pass symbol values; prefer .const/.equ
for immutable constants. Object relocation expressions are deliberately narrower
than absolute assembly expressions, as specified in OBJECT_FORMAT.md.
