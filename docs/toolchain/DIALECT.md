# Assembly dialect

Identifiers are case sensitive; instruction names and register aliases are case
insensitive. Labels use `name:`. Comments use semicolon or // outside quoted
strings. Operands are comma-separated; memory is `[register +/- bytes]`. Expressions
accept decimal/hex/binary integers, symbols, unary + - ~ and binary
* / % + - << >> & ^ | with conventional precedence. Register aliases appear in
the architecture register table. Numeric local `1f/1b` labels are not implemented;
use named labels or macro-local %% names.

```asm
.arch mica32
.const VALUE,21
.macro twice reg
    add $reg,$reg
.endm
.if VALUE
    li8 a0,VALUE
    twice a0
.else
    li8 a0,0
.endif
.assert VALUE-20
wfi
```

`.macro name param1,param2` ends with .endm; substitute parameters with $name.
%%label names receive a unique expansion prefix. Nested expansion is bounded.
`.repeat count`/`.endrepeat` uses $index for the 0-based iteration, at most 1024.
`.if expression`/`.else`/`.endif` evaluates constants available at preprocessing
time, with at most 64 conditional levels. .const/.equ define immutable constants;
.set permits reassignment. .include and .incbin take quoted relative paths. The
former expands source, the latter inserts bounded bytes.

`.byte/.half/.word/.quad` emit little-endian values; .ascii and .asciz emit quoted
strings, with escapes for newline, carriage return, tab, NUL, quote, backslash and
hexadecimal bytes. .space count[,fill] emits bytes, .align uses a power-of-two byte
boundary up to 4096, and .org moves forward with padding. .assert
expression[,message] fails on zero and .error message always fails.
.global/.globl/.weak/.extern are supported with -c. Section-name markers do not
reorder output or create independent sections.

Pseudos: ret=jr x6; push/pop use XLEN-byte stack slots. Object-mode li32/li64
have fixed 8/24-byte expansions for relocation. Standalone numeric li32 in
MICA-32 2.0 can shrink to li8 or set16 after range validation. li chooses a short
literal form when known and otherwise a long form. Use li32/li64 for forward
addresses to avoid unstable sizing. Vector
vclear/vmacc are software expansions described in SIMD.md. No optimizer changes
MMIO, memory ordering, traps or atomic operations.

Scalar arithmetic accepts destination, first source, second source in addition
to the short destructive destination, second source syntax. A three-operand form
uses the short encoding when destination equals the first source and both
registers are below x8; otherwise it selects the existing ALU3 encoding. Explicit
add3/sub3 and peers always retain their long form. A high-register mov expands
to existing add-with-zero. Register and extension requirements still apply.

```asm
.arch mica32v2
li x1,21
add x1,x1,x1
mov x9,x1
add3 x2,x1,x0
stop
```

The example requires X because x9 is an expanded register. The documentation
test assembles it with X enabled. No new hardware instruction or alias spelling
is introduced by this selection rule.
