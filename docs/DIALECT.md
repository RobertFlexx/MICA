# MICA assembler dialect  -  implemented reference

The assembler `mica-as` is a single translation-unit, C++23 binary emitter. It uses a **two-pass symbol resolver** with fixed pseudo-instruction sizes. Unlike a toolchain for ELF/PE/Mach-O, it does not produce relocatable objects, symbols for an external linker, DWARF, or position-independent linking. It emits raw flat memory images, an optional listing, and an optional Intel HEX file.

## CLI

```sh
./build/mica-as --help
./build/mica-as --xlen 32 examples/hello32.mica -o hello.bin --listing hello.lst --hex hello.hex
./build/mica-as --xlen 64 --xreg --mul --simd --atomic --flow program.mica -o program.bin
./build/mica-run --xlen 64 --simd --atomic --peek 0x100:16 program.bin
```

Flags select instructions legal in the binary. There is no automatic CPU feature-discovery negotiation. `.arch mica32` or `.arch mica64` checks selected XLEN against source.

## Complete implemented native mnemonic families

| Width | Names | Operands |
|---|---|---|
| 16 | `nop`,`wfi`,`fence`,`fence.i`,`ecall`,`eret` | none |
| 16 | `mov`,`add`,`sub`,`and`,`or`,`xor`,`shl`,`shr`,`sar`,`slt`,`sltu`,`seq`,`mul` | `d,s` |
| 16 | `not`,`neg`,`jr`,`jalr` | `d` |
| 16 | `li8`,`addi`,`andi`,`shli`,`shri` | `d,imm` |
| 16 | `bz`,`bnz` | `d,target` |
| 16 | `b` | `target` |
| 16 | `ldw`,`stw`,`ldh`,`sth`,`ldb`,`stb`,`ldhu`,`ldbu` | `d,[base +/- offset]` |
| 32 | `add3`,`sub3`,`and3`,`or3`,`xor3`,`shl3`,`shr3`,`sar3`,`slt3`,`sltu3`,`seq3`,`mul3` | `d,a,b` |
| 32 | `add3i`,`and3i`,`or3i`,`xor3i`,`shl3i`,`shr3i`,`sar3i` | `d,a,imm` |
| 32 | `movhi`,`movlo`,`li16` | `d,imm16` |
| 32 | `beq`,`bne`,`blt`,`bge`,`bltu`,`bgeu` | `a,b,target` |
| 32 | `j`,`call` | `target` |
| 32 | `csrr` | `d,csr` |
| 32 | `csrw` | `csr,source` |
| 32+A | `lr.w`,`lr.q` | `d,[base]` |
| 32+A | `sc.w`,`sc.q`,`amoadd.w`,`amoswap.w`,`amoadd.q`,`amoswap.q` | `d,value,[base]` |
| 32+XLEN64 | `addw3`,`subw3`,`shlw3`,`shrw3`,`sarw3`,`andw3`,`orw3`,`xorw3`,`mulw3` | `d,a,b` |
| 32+XLEN64 | `ldq`,`stq`,`ldws`,`ldwu`,`ldbs`,`ldhs` | `d,[base +/- offset]` |
| 32+V | `vadd`,`vsub`,`vmul`,`vand`,`vor`,`vxor`,`vshl`,`vshr`,`vsar`,`vmin`,`vmax`,`vcmpeq`,`vcmplt`,`vdot8`,`vziplo`,`vziphi`,`vunziplo`,`vunziphi` | `stem.type[.sat][.rnd] vd,va,vb` |
| 32+V | `vabs`,`vneg` | `stem.type vd,va` |
| 32+V | `vld`,`vst` | `vd,[base]` |
| 16+F | `ldpi.b/h/w/q`, `stpi.b/h/w/q` | `d,[base]` |
| 32+F | `ldpi.b/h/w/q`, `stpi.b/h/w/q` | `d,[base],stride` |
| 32+F | `dbnz` | `counter,target` |

Suffix type is required for typed SIMD ops, one of `u8,s8,u16,s16,u32,s32,u64,s64`. `vdot8` only accepts 8-bit type; `.sat` only allowed on `vadd/vsub/vmul`; `.rnd` only allowed on `vshr/vsar`. Any duplicate or invalid modifiers are errors.

## Pseudo-instructions

`ret`, `push r`, `pop r`, `li r,value`, `li32 r,value`, `li64 r,value` (64 only), `vclear v0`, and `vmacc.type[.sat][.rnd] vd,va,vb,tmp` expand into one or more real instructions. `push/pop` use the stack pointer alias `sp=x7` and cannot target the SP register. Explicit 64-bit loads/stores use `.q` because `.w` has its own zero/sign-extension behaviors.

## Directives

| Directive | Purpose |
|---|---|
| `.arch mica32 / .arch mica64` | Assert selected mode |
| `.text`, `.data`, `.rodata`, `.bss` | Human-readable markers, *all flattened into one image* |
| `.equ SYMBOL, EXPR` | Define symbol using already-known constants/labels; no redefinition |
| `.set SYMBOL, EXPR` | Set constant; use sparingly, as v1.0 resolves globally rather than preserving historic per-line values |
| `.align N` | Align to power-of-two byte boundary (1..4096), filling with 0 |
| `.org N` | Pad memory image with zero bytes to absolute byte address, no backwards seek |
| `.space COUNT [,BYTE]` | Emit repeated bytes (default zero) |
| `.byte`,`.half`,`.word`,`.quad` | Emit 1/2/4/8-byte little-endian numeric values |
| `.ascii "..."`, `.asciz "..."` | Emit ASCII/UTF-8 bytes, with or without `0` terminator |
| `.include "path"` | Recursive source inclusion relative to containing source file, depth-limited |
| `.macro NAME arg1, arg2` ... `.endm` | Expand named macro with `$arg1`, `$arg2`; `%%local` labels become unique per expansion |
| `.repeat N` ... `.endrepeat` | Repeat block N times; `$index` expands to 0..N-1 |

Expressions: decimal, hex `0x...`, binary `0b...`, references to already/ultimately resolved labels, unary `+ - ~`, parentheses, `+ - * / % << >> & ^ |`. Arithmetic is unsigned modulo 64 bits for expression evaluation; small signed immediate ranges are checked after reinterpretation as two's-complement. Division by zero and shifts at least 64 are errors. `.repeat` counts are **compile-time literals** or symbols already established by preprocessing. The assembler has line/file diagnostics and rejects invalid register feature combinations and out-of-range immediates.

Comments: `;` and `//` outside quoted strings. Mnemonics are case-insensitive. Labels are case-sensitive and may contain letters, digits, underscores, periods and dollar signs, but cannot begin with a digit.

**Known limitations:** no conditional assembly, no compiler-generated relocations, no relaxation, no 64-bit unsigned expression division signedness, no floating point, no ELF linking, `.equ` must be defined before use in expression contexts needing an immediate during first pass, sections are not real linker sections, program image limited to 32 MiB, recursive preprocessor deliberately bounded. Macros should use unique labels `%%name`; there is no namespace isolation across included files.

## Typed SIMD example

```asm
.arch mica32
li32 x1, samples1
li32 x2, samples2
li32 x3, output
vld v0, [x1]
vld v1, [x2]
vadd.s16.sat v2, v0, v1
vshr.s16.rnd v3, v2, v1
vst v3, [x3]
wfi
.align 16
samples1: .space 16
samples2: .space 16
output: .space 16
```

## Macros, string data, loops

```asm
.macro zero_then_inc r
    mov $r, x0
    addi $r, 1
.endm
.macro countdown r
%%loop:
    addi $r, -1
    bnz $r, %%loop
.endm
.arch mica32
li8 x1, 7
countdown x1
zero_then_inc x1
wfi
```

## MICA 1.0 flow syntax

Build with `mica-as --flow`. Run with `mica-run --flow`. For the demonstrator, instantiate `mica_core` with `FLOW=1`.

| Form | Meaning | Encoding |
| --- | --- | --- |
| `ldpi.b r,[p]`, `.h`, `.w`, `.q` | load from p and advance by element size | 16-bit if registers below 8 |
| `stpi.b r,[p]`, `.h`, `.w`, `.q` | store to p and advance by element size | 16-bit if registers below 8 |
| `ldpi.w r,[p],-8` | load and advance pointer by signed byte stride | 32-bit |
| `stpi.b r,[p],0` | store repeatedly to one address | 32-bit |
| `dbnz count,label` | decrement count, jump if nonzero | 32-bit |

`.q` needs XLEN64. The base pointer must be nonzero and different from the load destination / store source. A memory operand for streaming is always `[xN]`, never `[xN+offset]`. Stride is separate and signed 14-bit. If the counter starts at zero, `dbnz` wraps rather than stopping, so guard zero-length loops with `bz` before entering them.

```asm
.arch mica32
li32 x1, dest
li32 x2, src
li8 x3, 8
bz x3, copied
copy:
    ldpi.b x4, [x2]
    stpi.b x4, [x1]
    dbnz x3, copy
copied: wfi
src:  .byte 1,2,3,4,5,6,7,8
dest: .space 8
```

F is intentionally small. There are no hidden loop registers, condition-code dependencies or implicit DMA operations. A linker and ISA-aware debugger are still needed for a complete toolchain.

## B and T syntax

`--bitops` enables B instructions such as `popcnt3 x1,x2`, `rev8 x3,x4`, `bset3 x1,x2,x3` and `ror3 x1,x2,x3`. B is major 11 and all encoded instructions occupy four bytes. `--trap` selects trap behavior in the emulator, not a new encoding. The assembler accepts `--trap` for CLI symmetry. Examples: `examples/bitops32.mica`, `examples/bitops64.mica`, `examples/trap32.mica`, and `examples/trap_irq32.mica`. `csrr x1,features`, `csrr x2,arch`, and `csrr x3,instret_lo` are valid on a base build. Full semantics: [EXTENSIONS.md](EXTENSIONS.md).
