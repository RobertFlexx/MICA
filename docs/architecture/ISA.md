# MICA 1.0 scalar compatibility reference

MICA 2.0 overrides specific rules in [MICA2.md](MICA2.md). This manual, the compatibility rules in the [CSR map](CSR.md),
[exceptions](EXCEPTIONS.md), [memory model](MEMORY_MODEL.md), [SIMD](SIMD.md) and
[ABI](ABI.md) define MICA 1.0. Proposals in research documents do not add
architectural behavior. Undefined/reserved encodings are illegal, never NOP. The
machine-readable 1.0 allocation is `isa/encodings/mica1.json`; the
[generated tables](ENCODINGS.md) describe the current 2.0 superset.

## State and notation

XLEN is 32 or 64. Registers x0..x7 are required; optional X adds x8..x15. x0 always
reads zero and ignores writes. All operands are read before any instruction writes a
register. D/A/B/S name the registers identified in the format table. `sextN`
interprets N low bits as two's complement and extends to XLEN; `zext` fills with
zero. Booleans are XLEN-wide integers 0 or 1. Arithmetic and effective addresses
wrap modulo 2^XLEN. There are no flags, arithmetic overflow exceptions or branch
delay slots. Multiplication returns low bits; no scalar divide opcode is allocated.
The assembly `mica_udivmod` helper returns quotient zero and remainder dividend for
a zero divisor.

Reset establishes PC=0, x1..x6=0 and SP=`(RAM_BYTES-16)&~15`. X registers reset zero
when present. CSR state follows the CSR table. Platform RAM contents are
image/startup responsibilities; reset does not erase SRAM. The emulator's otherwise
unloaded RAM starts zero, which is a platform convenience.

## Encoding and fetch

Instructions start at even byte addresses and contain two or four bytes. Read the
first little-endian halfword H. If H[15:14] != 11, its length is two; otherwise read
another halfword L at PC+2 and its length is four. The long major is H[13:10];
payload P is `{H[9:0],L[15:0]}`. Thus instruction bitfield notation is not a
conventional little-endian uint32 envelope. The retirement `insn` field **is** the
byte-image uint32, `H | (L << 16)`.

Short formats: R uses op8 H[13:6], d H[5:3], s H[2:0]; I uses op3 H[13:11], d
H[10:8], imm8 H[7:0]; M uses op3 H[13:11], data H[10:8], base H[7:5], off5 H[4:0].
Long formats and all exact payload fields are in ENCODINGS.md. Majors 12..15 and
unallocated suboperations are reserved. Unused bits must be zero. Naming x8..x15
without X is illegal even if the destination would be ignored or memory addressing
otherwise succeeds.

No instruction is executed using an incomplete fetch. A second-parcel fault reports
the original instruction PC and the second parcel's address. A fetch buffer may read
aligned words but must preserve these halfword semantics. Instruction/data bytes are
coherent in the emulator. RTL invalidates its one word reuse buffer on every store,
redirect, trap and `fence.i`.

## PC and branches

`sequentialPC = (PC+length) mod 2^XLEN`. Relative displacements are signed halfword
counts added to sequentialPC, then wrapped to XLEN. Short `bz/bnz` use imm8, short
`b` uses H[10:0] as imm11, long comparisons use rel14, `dbnz` uses rel20 and
`j/call` use rel24. Register jumps use the old register value. Calls write
x6=sequentialPC. An odd destination faults at the jump, before writing x6 or any
other destination. An even unmapped destination faults on its subsequent fetch,
after the jump has retired.

## Scalar computation

The generated instruction table specifies each operator. Short binary R operations
update their first operand; long ALU operations have independent destination and
sources. Register shifts mask the count by XLEN-1; short immediate shifts require
0..31 even on XLEN64; long shifts require 0..XLEN-1. All higher immediate shift bits
are reserved. Arithmetic right shifts replicate the operand's sign. Signed
comparisons use XLEN-bit two's complement values. `movhi` replaces the entire
register with zext(imm16<<16), `movlo` changes only low 16, and `li16/li8` sign
extend. XLEN64 W operations use low 32 sources, mask shifts by 31 and sign extend
every 32-bit result, including logical ones.

## Memory and flow

Memory is byte addressed and little endian. Natural alignment is required for
2/4/8-byte scalar and 16-byte vector accesses. Short memory displacement is
sext(off5) times access width; long memory displacement is a signed **byte** offset.
The base need not itself be aligned if the final address is aligned. `ldw` zero
extends on XLEN64; `ldh/ldb` sign extend; `ldhu/ldbu` zero extend. The long XLEN64
`ldws/ldbs/ldhs` sign extend, `ldwu` zero extends and `ldq` loads all 64 bits.
Stores use the corresponding low bits. Stores return a completion response and
retire only after success. A failed store must not modify target memory. A load into
x0 still performs the access and may fault.

Compact F instructions use R op8=23..30, with data=d and base=s. Long F uses major
10, op4/data4/base4/stride14. Load results are always zero extended. Address is the
**old** base. On success only, update base by width (compact) or sext(stride14)
(long). Base=x0 or base=data is illegal for loads and stores. The assembler chooses
compact form only with two short-register operands; explicit stride always forces
long form. `dbnz` decrements a nonzero-index counter modulo XLEN and branches if its
new value is not zero. An old zero counter therefore wraps; it is not a zero-trip
loop.

## System behavior and precise effects

`fence` orders all preceding memory transactions before subsequent ones. `fence.i`
additionally synchronizes instruction fetch. On the single-outstanding uncached core
these require no extra transactions. Legacy `wfi` retires and halts execution.
Without T, `ecall` also halts. With T it enters cause 11 and saves **next PC** in
EPC. `eret` requires T and an active handler, restores PC/IE
and clears handler state. Reserved operands in system/unary instructions are
illegal.

Synchronous faults preserve the faulting instruction's register and memory state. No
destination/base update or link write may escape an illegal or failed instruction.
Earlier retired instructions remain committed. Faults do not increment instret. T
ecall does increment instret. Interrupts occur at an instruction boundary and do not
increment instret. Without a usable trap vector, or during an active handler, faults
terminate execution with fault set.

## Profiles and conformance

MICA-C: XLEN32/eight registers/base. MICA-E adds M/F/B/T. MICA-64 uses XLEN64, 16
registers and M/F/B/T. Optional PERF counters are discovered independently. MICA-DSP
is an emulator configuration; V hardware is absent. MICA-MP remains a non-runnable
proposal. The profile manifest and `features/arch` CSRs are the discovery
mechanisms. See REGISTERS.md for aliases and CSR.md for rights.

Canonical disassembly uses explicit real instruction names and xN/vN registers. No
pseudoinstruction has a distinct encoding. `li32`, `li64`, `push`, `pop`, `ret`,
`li`, `vclear` and `vmacc` expand in the assembler. In particular li32 uses
movhi/movlo; li64 uses movhi, movlo, shl3i16, movlo, shl3i16, movlo. Disassembly
reconstructs real instructions; illegal bytes use `.half/.byte`.

Conformance tests: `tests/integration.py` (scalar, B/F/A/V and ABI),
`tests/engineering.py` (faults, toolchain and malformed input),
`tests/fast_paths.py` (engines), `verification/differential/run.py` (RTL32/64, all
scalar families, reserved opcodes, bus delays, faults and interrupts). Encoding
round trips include every possible short halfword in a byte stream and deterministic
random long envelopes. Execution coverage is detailed in
[coverage limits](../verification/COVERAGE.md).
