# MICA-32/64 v1.0 ISA technical reference

**Authority:** this is a proposed ISA. For independently executable scalar/A/V semantics, compare `toolchain/assembler.cpp` with `sim/emulator.cpp`. The hardware core implements only the stated subset. This document aims to be normative for the software prototype, not silicon certification.

## 1. The programmer's model

- `XLEN`: **32** or **64** bits selected when creating the machine. Each scalar register and the PC holds XLEN bits.
- `x0` is hardwired zero. `x1..x7` are the only mandatory registers. Optional **X** adds `x8..x15`, addressable only by extended 32-bit encodings. The hardware register file has 16 entries to facilitate the X variant; a future area-optimized eight-entry core should eliminate the unused entries.
- Registers named `a0..a3` alias `x1..x4`, `t0/fp` alias `x5`, `lr=x6`, and `sp=x7`.
- All instructions are aligned to a **2-byte** boundary. Every instruction is exactly **2 or 4 bytes**. The top two bits of the *first* 16-bit halfword are `11` for 32-bit extended instructions, otherwise the instruction is one halfword.
- Instruction memory, stack and data are little-endian. Extended 32-bit instruction bit fields are logical `{first-halfword bits,second-halfword bits}` as shown below, not an ordinary machine little-endian uint32.
- Scalar calculations wrap modulo `2^XLEN`, except defined 64-bit W32 operations and comparisons. Signed numbers use two's complement. Signed right shifts are arithmetic. Register shifts are modulo XLEN, immediate shifts must be less than XLEN. `x0` writes are ignored.
- Natural alignment is required for 2/4/8-byte data. Misaligned memory accesses are faults. There are no branch delay slots, no condition flags, and no automatic program-address canonicalization.
- The minimum core uses in-order memory operations and no caches or external fabric. A multi-hart core must explicitly implement the chosen shared-memory and device ordering model.
- The v1.0 simulator maps memory in a flat byte array, starts PC=0, sets SP to `(RAM_SIZE-16)&~15`, and stops on `wfi/ecall` without the T option. With T enabled, `ecall` performs a machine-only software trap; see [EXTENSIONS.md](EXTENSIONS.md).

## 2. ABI draft (subject to compiler-driven revision)

`x1..x4` are arguments 0..3. Return value in `x1`; multi-result helper `mica_udivmod` uses x1=quotient and x2=remainder. `x5` is callee preserved and may serve as frame pointer. `x6` is the link register overwritten by `call/jalr`, saved by routines making nested calls. `x7` is stack pointer, which grows down. Stack must be **16-byte aligned at call boundaries**. `x1..x4` are caller saved. X extension: x8..x11 caller saved, x12..x15 callee saved. No red zone. There is no varargs, TLS, dynamic linker, unwind metadata or exception personality in this SDK.

`ret` expands into `jr x6`. `push r` and `pop r` are pseudo-instructions that allocate/restore 4 bytes in 32-bit mode, and 8 bytes in 64-bit mode. They can break call-boundary alignment if used without additional stack adjustment. These are not atomic and cannot preserve registers across interrupts without an interrupt ABI.

## 3. Scalar 16-bit formats

```text
R  15..14=00 | 13..6 op8 | 5..3 rd3   | 2..0 rs3
I  15..14=01 | 13..11 op3| 10..8 rd3  | 7..0 imm8
M  15..14=10 | 13..11 op3| 10..8 reg3 | 7..5 base3 | 4..0 off5
```

### R opcode (op8) enumeration

| op8 | Mnemonic | Exact semantics |
|---:|---|---|
| 0 | `nop` | no change; `rd=rs=0` required |
| 1 | `mov d,s` | `d=s` |
| 2,3 | `add`, `sub` | `d = d (+,-) s`, wrapping XLEN |
| 4,5,6 | `and`, `or`, `xor` | `d = d op s` |
| 7,8,9 | `shl`, `shr`, `sar` | `d` shifted by `s & (XLEN-1)` |
| 10,11,12 | `slt`, `sltu`, `seq` | compare `d` and `s`, store boolean in `d` |
| 13 | `jr d` | PC = d, rs=0 |
| 14 | `jalr d` | `lr=PC+2`; PC=d; rs=0 |
| 15,16 | `not`, `neg` | unary complement, two's complement negative; rs=0 |
| 17 | `mul` | low XLEN bits of product, M extension only |
| 18,19,20,21,22 | `wfi`, `fence`, `ecall`, `eret`, `fence.i` | system opcodes; all operand fields zero; see §8 |

`fence` is a full order barrier in the proposed multicore memory model. On the sequential one-hart simulator and minimal uncached RTL it is operationally a no-op. `fence.i` is an instruction-stream synchronization point; software simulators have coherent code bytes, while RTL instruction caching is absent. `eret` requires the optional T trap mechanism in the RTL. The T emulator checks an active handler before returning to `epc`. `wfi` still stops both reference engines, while `ecall` traps with T enabled and stops in the legacy base profile.

### I opcode (op3) enumeration

| op3 | Mnemonic | Semantics |
|---:|---|---|
| 0 | `li8 rd,imm8` | sign extend signed 8-bit literal |
| 1 | `addi rd,imm8` | add signed 8-bit literal |
| 2 | `andi rd,imm8` | AND unsigned 8-bit mask |
| 3,4 | `shli`, `shri` | unsigned immediate 0..31; upper 3 immediate bits zero |
| 5,6 | `bz`, `bnz` | test register against zero; signed 8-bit halfword offset from PC+2 |
| 7 | `b` | unconditional signed 11-bit halfword offset from PC+2; bits 10..8 share rd field |

### M opcode (op3) enumeration

| op3 | Mnemonic | Data width/extension | Byte displacement |
|---:|---|---|---|
| 0,1 | `ldw`, `stw` | 32-bit load zero-extended to XLEN / 32-bit store | signed off5 ×4 |
| 2,3 | `ldh`, `sth` | signed 16-bit load / 16-bit store | signed off5 ×2 |
| 4,5 | `ldb`, `stb` | signed 8-bit load / 8-bit store | signed off5 ×1 |
| 6,7 | `ldhu`, `ldbu` | unsigned halfword / unsigned byte load | signed off5 ×(2,1) |

`ldw` in MICA-64 **zero extends 32 bits**. Use `ldws` for signed 32-bit load in MICA-64. Loads and stores use `rd` as destination or source, respectively. Offsets are specified in bytes in assembly, and the assembler verifies scaling and range. All accesses must be naturally aligned.

## 4. Extended instruction envelope

```text
first halfword: [15:14]=11 [13:10]=major4 [9:0]=payload[25:16]
next halfword: [15:0]=payload[15:0]
```

The 32-bit machine operation is defined by `major` and 26-bit payload:

| Major | Payload layout (MSB to LSB) | Semantics |
|---:|---|---|
| 0 | `op6 rd4 ra4 rb4 zero8` | 3-operand XLEN ALU |
| 1 | `op4 rd4 ra4 imm14` | register-immediate XLEN ALU |
| 2 | `op6 rd4 imm16` | `movhi`,`movlo`,`li16` |
| 3 | `op4 ra4 rb4 rel14` | conditional signed/unsigned comparisons |
| 4 | `op2 rel24` | relative long `j`,`call` |
| 5 | `op6 rd4 ra4 rb4 aux8` | CSRs and A extension |
| 6 | `op6 vd3 va3 vb3 lane2 mode3 zero6` | packed SIMD V |
| 7 | `op6 rd4 ra4 rb4 zero8` | XLEN64-only 32-bit W operations |
| 8 | `op4 reg4 base4 off14` | XLEN64 load/store with signed byte offset |
| 9 | `op2 counter4 rel20` | F: `dbnz` |
| 10 | `op4 reg4 base4 stride14` | F: extended streaming load/store |
| 11 | `op6 rd4 ra4 rb4 zero8` | B bit operations (optional) |
| 12..15 | reserved | illegal instruction |

**major0 op6:** `add3=0,sub3=1,and3=2,or3=3,xor3=4,shl3=5,shr3=6,sar3=7,slt3=8,sltu3=9,seq3=10,mul3=11(M)`.

**major1 op4:** `add3i=0` (signed imm14), `and3i=1`, `or3i=2`, `xor3i=3` (unsigned imm14), `shl3i=4,shr3i=5,sar3i=6` (shift counts 0..XLEN-1; all otherwise unused bits zero).

**major2 op6:** `movhi=0` sets full register to `imm16<<16`, zero above bit31; `movlo=1` overwrites only the low 16 bits of the destination; `li16=2` sign extends imm16 to XLEN.

**major3 op4:** `beq=0,bne=1,blt=2,bge=3,bltu=4,bgeu=5`; relative 14-bit signed *halfword* displacement from PC+4.

**major4 op2:** `j=0,call=1`; signed 24-bit halfword displacement from PC+4. `call` stores PC+4 in x6.

**major7 op6 (XLEN64 only):** `addw3=0,subw3=1,shlw3=2,shrw3=3,sarw3=4,andw3=5,orw3=6,xorw3=7,mulw3=8(M)`. Use input bits 31..0 (shift modulo32), do 32-bit arithmetic, and **sign-extend result** to 64 bits, matching the common RV64 W-result convention without sharing binary encodings. Logical W operations also sign extend (unlike native XLEN64 bitwise ALU). All reserved bits must be zero.

**major8 op4 (XLEN64 only):** `ldq=0,stq=1,ldws=2,ldwu=3,ldbs=4,ldhs=5`; 14-bit *signed byte* displacement, with natural alignment. `ldq/stq` transfer 64 bits. `ldws` sign extends a 32-bit word to 64 bits, `ldwu` zero extends, `ldbs` sign extends a byte, `ldhs` a halfword. Short-form `ldb/ldh` remain available in XLEN64. All unused opcodes are reserved.

## 5. 64-bit constant loading

`li64 rd,0x0123456789abcdef` is a **six-instruction pseudo-instruction**, without any temporary register: `movhi high16; movlo next16; shl3i 16; movlo next16; shl3i 16; movlo low16`. `li32` is two instructions (`movhi;movlo`), and in XLEN64 it writes a *zero-extended* 32-bit bit-pattern. `li` picks `li8` or `li16` if signed literal fits (and register is short-encodable), otherwise `li32` (XLEN32) or `li64` (XLEN64). A forward symbol always takes the long form; the assembler deliberately performs no branch or immediate relaxation. Explicit `li32/li64` are preferred in generated compiler output to keep sizes predictable.

## 6. Atomic extension A and memory ordering

**Major5 op6:** `csrr=0,csrw=1,lr.w=2,sc.w=3,amoadd.w=4,amoswap.w=5,lr.q=6,sc.q=7,amoadd.q=8,amoswap.q=9`; `.q` is XLEN64-only. CSR ID is in `aux8`, other unused fields zero. Atomic memory operand is `[ra]`, with zero displacement and natural alignment. The returned LR or AMO old value for `.w` is zero-extended to XLEN; `sc.w/.q` return zero on success and one on failure. The proposed consistency baseline is sequential consistency for atomics on the *same address* with explicit `fence` needed to order other regular/device operations; this is less fully specified than the ratified RISC-V RVWMO model.

**Unresolved for real silicon:** the full cross-location memory model, LR/SC fairness/progress, acquire/release variations, reservation granularity, coherent DMA, MMIO ordering and multi-hart cache protocol. These must be formalized **before** any multicore silicon claim. The one-hart simulator implements a reservation and correct sequential behavior for basic tests, not a global coherent multicore interconnect. The provided RTL does not implement A.

**CSR names:** `coreid=0, status=1, epc=2, cause=3, tvec=4, ie=5, ip=6, cycle_lo=7, cycle_hi=8, timer_lo=9, timer_hi=10, cmp_lo=11, cmp_hi=12, vec_dirty=13, vec_enabled=14`. `features=15, arch=16, instret_lo=17, instret_hi=18` are read-only discovery and retirement CSRs. Other IDs 19..255 reserved; the emulator's storage is permissive for experimentation, but software must not infer standard semantics from otherwise unspecified CSRs. In a future privileged core, machine-mode, priority masks, interrupt entry/return rules and saved state will be mandatory.

## 7. Vector extension V

The optional 128-bit vector state is `v0..v7` (8 registers; all writable) per hart. The bit packing is little endian (lane0 occupies the low bits). `lane2={8,16,32,64}` for codes 0..3. `mode3.bit0` controls signedness, `bit1` saturation for add/sub/mul, and `bit2` round-to-nearest, ties to even for right shifts. Each lane of `v0..v7` is processed independently except the indicated shuffles/dot-products. Vector state adds 1024 bits per hart; lazy state preservation requires safe privileged tracking and cannot be assumed merely from the `vec_dirty` CSR name.

**Opcode enumeration:** `vadd=0,vsub=1,vmul=2,vand=3,vor=4,vxor=5,vshl=6,vshr=7,vsar=8,vmin=9,vmax=10,vcmpeq=11,vcmplt=12,vabs=13,vneg=14,vdot8=15,vld=16,vst=17,vziplo=18,vziphi=19,vunziplo=20,vunziphi=21`.

- Typed operation example: `vadd.s16.sat v0,v1,v2`. Types `.u8/.s8/.u16/.s16/.u32/.s32/.u64/.s64` are explicit. Saturation clamps to the full mathematical result to the representable signed/unsigned lane range, so saturated multiplication needs a double-width intermediate.
- Unsaturated add/sub/mul wrap modulo lane width. `.rnd` is valid only for `vshr` and `vsar` and rounds the quotient of division by `2^shift` to the nearest integer, ties to even. Shift count comes from the corresponding lane in `vb`, modulo lane bit width.
- `vcmpeq/vcmplt` write all ones or all zeros per lane; `vcmplt` uses signed comparison for `.sN`.
- `vabs`/`vneg` are unary and wrap on the most-negative signed value. `vmin/vmax` use the indicated signedness.
- `vdot8.s8/u8 v0,v1,v2`: 4 independent dot products, each sums 4 signed/unsigned 8-bit element-products, and writes four 32-bit lanes, wrapping the sum to 32 bits.
- `vziplo/ziphi`: interleave the low/high half of the source vector lanes. `vunziplo/unziphi`: collect respectively the even/odd source lanes, half from source A and half from source B.
- `vld v0,[x1]` and `vst v0,[x1]`: exactly 16 byte-aligned vector memory operations, no offset. The vector fields use the scalar base in `va3`; type/lane/mode/reserved lower bits must be zero.
- `vmacc.s16 v0,v1,v2,v7`: *pseudo*, two operations `vmul.s16 v7,v1,v2` then `vadd.s16 v0,v0,v7`; scratch must differ from the 3 actual data operands. It is not a true fused/accumulator instruction.

The **reference emulator** runs V; the **minimal RTL does not**. A physical extension must decide between a full 128-bit datapath, segmented execution (e.g., 4x32), and deliberate cycle/energy trade-offs. SIMD state must be saved on task switch once used.

## 8. Exceptions, interrupts, multicore and privilege: proposal vs reality

Proposed P extension would provide:

1. Machine/user privilege separation (and optionally an RTOS supervisor mode), with MPU regions and execute/write permissions.
2. `epc/cause/tvec/status/ie/ip` atomic trap-state update, interrupt masking, aligned trap vectors, separate stacks, and interrupt priority/latency contract.
3. `cycle` and monotonic timer/comparator with per-hart interrupt, `wfi` wakeup from eligible interrupts.
4. Context switch savings (8 scalar registers) and optional lazy SIMD save/restore with access faults until re-enabled. Proper lazy SIMD support requires no cross-task data leakage.
5. Bus arbitration and global coherence for A; optional shared cache and shared SRAM segments. An RTOS scheduler is software: it is not automatically provided by an ISA instruction.

**None** of this is completely implemented in the supplied RTL. The runtime `ecall` stop is a simulator convenience, not a real privilege trap. Claiming multicore execution or hard real-time guarantees would be misleading at v1.0. A rigorous trap/ordering contract and verification are left as an open design task after 1.0.

## 9. Compatibility policy

No opcode shared with RISC-V. Previously defined major0..6 and 16-bit field positions from v0.1 remain identical. New major7..8 are XLEN64-only. Extensible reserved encodings **must fault** rather than silently act as NOPs. Version 1.0 binary format is an internal prototype. Do not burn v1.0 into mask ROM for a long-term product until the spec is frozen and conformance tested.

## 10. F extension: local flow fusion (MICA 1.0)

F targets pointer-heavy device-control loops. It is optional and must not appear in the C-only base profile. `--flow` enables it in `mica-as` and `mica-run`. The current RTL parameter is `FLOW=1`; `FLOW=0` must reject the new opcodes. This extension is architectural and implemented in the scalar RTL, but that RTL has not passed independent HDL simulation or timing closure.

**Compact streaming R instructions.** R form `class=00`, with op8 values 23..30 and three-bit `data` and `base` register fields:

| op8 | Assembly | Transfer width | Base delta |
| ---: | --- | ---: | ---: |
| 23 | `ldpi.b d,[base]` | 1 byte, unsigned | +1 |
| 24 | `ldpi.h d,[base]` | 2 bytes, unsigned | +2 |
| 25 | `ldpi.w d,[base]` | 4 bytes, unsigned | +4 |
| 26 | `ldpi.q d,[base]` | 8 bytes, unsigned, XLEN64 only | +8 |
| 27 | `stpi.b d,[base]` | 1 byte | +1 |
| 28 | `stpi.h d,[base]` | 2 bytes | +2 |
| 29 | `stpi.w d,[base]` | 4 bytes | +4 |
| 30 | `stpi.q d,[base]` | 8 bytes, XLEN64 only | +8 |

Load returns a zero-extended value, irrespective of XLEN. Store writes the low `8 * width` bits. Both read the **old** base as the address and increment that base after successful access. The base must not be x0 or the data register. Both registers must be x0..x7 in compact form. The assembler rejects source and base aliasing even on stores. The data address must be naturally aligned. An implementation that traps a memory error must not change the destination or base register for the faulting instruction. The present minimal hardware has no external bus fault input and therefore cannot provide this guarantee for failed external transactions.

**Extended streaming, major=10.** Payload bit positions:

```
[25:22] operation (0..7, order identical to compact ops)
[21:18] data register (0..15)
[17:14] base register (0..15)
[13:0]  signed 14-bit stride in BYTES, -8192 through +8191
```

The assembler uses the compact two-byte form for exactly two operands when both registers are x0..x7. Three operands force the four-byte form, such as `ldpi.b x4,[x2],-1`. When a register requires X, the assembler uses extended form even if the stride is omitted. Stride may be zero. The address is the old base and the updated base is `(base + sign_extend(stride)) modulo 2^XLEN`. The stride need not be a multiple of the element width; the next access must still meet its own alignment requirements. There are no hidden flags.

**Counted branch, major=9.** `dbnz counter,target` uses payload `op2=0`, `counter4`, signed `rel20` in **2-byte instruction parcels** relative to `PC+4`. First decrement the counter modulo `2^XLEN`, write it back, then branch if the new value is nonzero. Count zero therefore wraps and branches; software MUST guard entry when zero count is possible. `dbnz x0,target` is illegal, and assembler/emulator/RTL reject the zero counter. This semantic contract makes a one-instruction tail of counted loops with no separate status register or implicit loop state to save across task switches.

F does not introduce new interrupt-save state. Every instruction retires with ordinary scalar registers updated and does not survive a context switch in a hidden loop buffer. In a single-cycle memory with no faults, base update is part of the same retirement. In a pipelined or error-reporting implementation, it must commit only when memory succeeds. This constraint is part of the architecture, not a suggestion.

## 11. Encodings, code density and profile identity

A normal byte-copy iteration can be written as `ldbu; stb; addi; addi; addi; bnz` using 6 short instructions (12 bytes) or as `ldpi.b; stpi.b; dbnz` using 2 short and 1 long instruction (8 bytes). That is 3 instead of 6 dynamically decoded instructions. The 1.0 ISA can be smaller on this workload; not all programs will improve and no power number follows from the byte count alone.

The assembler command-line feature switches define the model at assemble time. Raw firmware does not currently encode target XLEN or extension capabilities in a header, so a loader must know the profile out-of-band. A future standardized executable format should include a feature bitmap, minimum memory requirement, ROM integrity and entry point.

## 11. B, T and feature-discovery additions (1.0 compatible)

Extended major 11 implements the optional B bit instructions. Details, field requirements, and trap semantics are in [EXTENSIONS.md](EXTENSIONS.md). Existing major numbers and 16-bit scalar encodings did not change. CSR IDs 15 and 16 report hardware capabilities and XLEN, and CSR IDs 17/18 report retired instructions. T reuses existing `ecall`, `eret` and CSR encodings. The reference emulator uses `--trap` to opt into T.
