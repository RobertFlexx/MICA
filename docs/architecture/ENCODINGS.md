# MICA 2.0 encoding allocation

Generated from `isa/encodings/mica2.json`. The first halfword is little endian; for a long instruction its top two bits are 11 and its bits 13:10 contain the major. Payload is `((first & 1023) << 16) | second`. Unallocated encodings are illegal.

## R

Short class 0. `op8[13:6] rd3[5:3] rs3[2:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `nop` | base | No state changes. |
| 1 | `mov d,s` | base | D = S. |
| 2 | `add d,s` | base | D = D + S. |
| 3 | `sub d,s` | base | D = D - S. |
| 4 | `and d,s` | base | D = D & S. |
| 5 | `or d,s` | base | D = D &#124; S. |
| 6 | `xor d,s` | base | D = D ^ S. |
| 7 | `shl d,s` | base | D = D << (S & (XLEN-1)). |
| 8 | `shr d,s` | base | D = unsigned(D) >> (S & (XLEN-1)). |
| 9 | `sar d,s` | base | D = signed(D) >> (S & (XLEN-1)). |
| 10 | `slt d,s` | base | D = signed(D) < signed(S). |
| 11 | `sltu d,s` | base | D = unsigned(D) < unsigned(S). |
| 12 | `seq d,s` | base | D = D == S. |
| 13 | `jr d` | base | nextPC = D; reject odd target before side effects. |
| 14 | `jalr d` | base | target = D; x6 = sequentialPC; nextPC = target; reject odd target before writing x6. |
| 15 | `not d` | base | D = ~D. |
| 16 | `neg d` | base | D = 0-D. |
| 17 | `mul d,s` | M | D = low_XLEN(D*S). |
| 18 | `wfi` | base | Retire and halt the current execution run. |
| 19 | `fence` | base | Complete preceding memory operations before following operations. |
| 20 | `ecall` | base | With T: enter cause 11 with EPC=sequentialPC. Without T: retire and halt. |
| 21 | `eret` | T | Require T and active handler; nextPC=EPC, restore saved IE and clear handler state. |
| 22 | `fence.i` | base | Synchronize instruction fetch with preceding stores; invalidate fetch reuse. |
## I

Short class 1. `op3[13:11] rd3[10:8] imm8[7:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `li8 d,imm` | base | D = sext(imm8). |
| 1 | `addi d,imm` | base | D = D + sext(imm8). |
| 2 | `andi d,imm` | base | D = D & zext(imm8). |
| 3 | `shli d,imm` | base | D = D << imm8; require imm8 < 32. |
| 4 | `shri d,imm` | base | D = unsigned(D) >> imm8; require imm8 < 32. |
| 5 | `bz d,target` | base | If D==0: nextPC=sequentialPC+2*sext(imm8). |
| 6 | `bnz d,target` | base | If D!=0: nextPC=sequentialPC+2*sext(imm8). |
| 7 | `b target` | base | nextPC=sequentialPC+2*sext(imm11). |
## MEM

Short class 2. `op3[13:11] data3[10:8] base3[7:5] off5[4:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `ldw d,[base+offset]` | base | D=zext(load32(A)). |
| 1 | `stw d,[base+offset]` | base | store32(A,low32(D)). |
| 2 | `ldh d,[base+offset]` | base | D=sext(load16(A)). |
| 3 | `sth d,[base+offset]` | base | store16(A,low16(D)). |
| 4 | `ldb d,[base+offset]` | base | D=sext(load8(A)). |
| 5 | `stb d,[base+offset]` | base | store8(A,low8(D)). |
| 6 | `ldhu d,[base+offset]` | base | D=zext(load16(A)). |
| 7 | `ldbu d,[base+offset]` | base | D=zext(load8(A)). |
## ALU

Extended major 0. `op6[25:20] rd4[19:16] ra4[15:12] rb4[11:8] zero8[7:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `add3 d,a,b` | base | D = A+B. |
| 1 | `sub3 d,a,b` | base | D = A-B. |
| 2 | `and3 d,a,b` | base | D = A&B. |
| 3 | `or3 d,a,b` | base | D = A&#124;B. |
| 4 | `xor3 d,a,b` | base | D = A^B. |
| 5 | `shl3 d,a,b` | base | D = A << (B & (XLEN-1)). |
| 6 | `shr3 d,a,b` | base | D = unsigned(A) >> (B & (XLEN-1)). |
| 7 | `sar3 d,a,b` | base | D = signed(A) >> (B & (XLEN-1)). |
| 8 | `slt3 d,a,b` | base | D = signed(A)<signed(B). |
| 9 | `sltu3 d,a,b` | base | D = unsigned(A)<unsigned(B). |
| 10 | `seq3 d,a,b` | base | D = A==B. |
| 11 | `mul3 d,a,b` | M | D = low_XLEN(A*B). |
## IMM

Extended major 1. `op4[25:22] rd4[21:18] ra4[17:14] imm14[13:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `add3i d,a,imm` | base | D = A+sext(imm14). |
| 1 | `and3i d,a,imm` | base | D = A & zext(imm14). |
| 2 | `or3i d,a,imm` | base | D = A &#124; zext(imm14). |
| 3 | `xor3i d,a,imm` | base | D = A ^ zext(imm14). |
| 4 | `shl3i d,a,imm` | base | D = A << imm14 ; require imm14 < XLEN. |
| 5 | `shr3i d,a,imm` | base | D = unsigned(A) >> imm14 ; require imm14 < XLEN. |
| 6 | `sar3i d,a,imm` | base | D = signed(A) >> imm14 ; require imm14 < XLEN. |
## WIDE

Extended major 2. `op6[25:20] rd4[19:16] imm16[15:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `movhi d,imm16` | base | D=zext(imm16 << 16), including on XLEN64. |
| 1 | `movlo d,imm16` | base | D=(oldD & ~65535) &#124; imm16. |
| 2 | `li16 d,imm16` | base | D=sext(imm16). |
| 3 | `adrpc d,imm16` | 2C | D=instruction_PC+2*sext(imm16), modulo XLEN. Intended for PC-relative literal addresses. |
## BR

Extended major 3. `op4[25:22] ra4[21:18] rb4[17:14] rel14[13:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `beq a,b,target` | base | If A==B: nextPC=sequentialPC+2*sext(rel14). |
| 1 | `bne a,b,target` | base | If A!=B: nextPC=sequentialPC+2*sext(rel14). |
| 2 | `blt a,b,target` | base | If signed(A)<signed(B): nextPC=sequentialPC+2*sext(rel14). |
| 3 | `bge a,b,target` | base | If signed(A)>=signed(B): nextPC=sequentialPC+2*sext(rel14). |
| 4 | `bltu a,b,target` | base | If unsigned(A)<unsigned(B): nextPC=sequentialPC+2*sext(rel14). |
| 5 | `bgeu a,b,target` | base | If unsigned(A)>=unsigned(B): nextPC=sequentialPC+2*sext(rel14). |
## J

Extended major 4. `op2[25:24] rel24[23:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `j target` | base | nextPC=sequentialPC+2*sext(rel24). |
| 1 | `call target` | base | x6=sequentialPC; nextPC=sequentialPC+2*sext(rel24). |
## SYS

Extended major 5. `op6[25:20] rd4[19:16] ra4[15:12] rb4[11:8] aux8[7:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `csrr d,csr` | base | D=readCSR(aux8); reject absent or reserved CSR. |
| 1 | `csrw csr,a` | base | writeCSR(aux8,A); reject absent, reserved or read-only CSR before effects. |
| 2 | `lr.w d,[a]` | A | Set reservation=(A,width); D=old memory value. RAM only; aligned, single-hart sequential reference behavior. |
| 3 | `sc.w d,b,[a]` | A | Test and clear reservation matching address AND width; on success store B; D=0 on success, 1 on failure. RAM only; aligned, single-hart sequential reference behavior. |
| 4 | `amoadd.w d,b,[a]` | A | D=old memory value; memory=old+B. RAM only; aligned, single-hart sequential reference behavior. |
| 5 | `amoswap.w d,b,[a]` | A | D=old memory value; memory=B. RAM only; aligned, single-hart sequential reference behavior. |
| 6 | `lr.q d,[a]` | A | Set reservation=(A,width); D=old memory value. RAM only; aligned, single-hart sequential reference behavior. |
| 7 | `sc.q d,b,[a]` | A | Test and clear reservation matching address AND width; on success store B; D=0 on success, 1 on failure. RAM only; aligned, single-hart sequential reference behavior. |
| 8 | `amoadd.q d,b,[a]` | A | D=old memory value; memory=old+B. RAM only; aligned, single-hart sequential reference behavior. |
| 9 | `amoswap.q d,b,[a]` | A | D=old memory value; memory=B. RAM only; aligned, single-hart sequential reference behavior. |
## V

Extended major 6. `op6[25:20] vd3[19:17] va3[16:14] vb3[13:11] lane2[10:9] mode3[8:6] zero6[5:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `vadd.uN vd,va,vb` | V | lane A+B. See SIMD modifier rules; emulator only. |
| 1 | `vsub.uN vd,va,vb` | V | lane A-B. See SIMD modifier rules; emulator only. |
| 2 | `vmul.uN vd,va,vb` | V | lane A*B. See SIMD modifier rules; emulator only. |
| 3 | `vand.uN vd,va,vb` | V | lane A&B. See SIMD modifier rules; emulator only. |
| 4 | `vor.uN vd,va,vb` | V | lane A&#124;B. See SIMD modifier rules; emulator only. |
| 5 | `vxor.uN vd,va,vb` | V | lane A^B. See SIMD modifier rules; emulator only. |
| 6 | `vshl.uN vd,va,vb` | V | lane A << (B&(bits-1)). See SIMD modifier rules; emulator only. |
| 7 | `vshr.uN vd,va,vb` | V | unsigned lane A >> (B&(bits-1)). See SIMD modifier rules; emulator only. |
| 8 | `vsar.uN vd,va,vb` | V | signed lane A >> (B&(bits-1)). See SIMD modifier rules; emulator only. |
| 9 | `vmin.uN vd,va,vb` | V | lane min(A,B). See SIMD modifier rules; emulator only. |
| 10 | `vmax.uN vd,va,vb` | V | lane max(A,B). See SIMD modifier rules; emulator only. |
| 11 | `vcmpeq.uN vd,va,vb` | V | lane all-ones if A==B, else zero. See SIMD modifier rules; emulator only. |
| 12 | `vcmplt.uN vd,va,vb` | V | lane all-ones if A<B, else zero. See SIMD modifier rules; emulator only. |
| 13 | `vabs.uN vd,va` | V | lane abs(A), wrapping. See SIMD modifier rules; emulator only. |
| 14 | `vneg.uN vd,va` | V | lane -A, wrapping. See SIMD modifier rules; emulator only. |
| 15 | `vdot8.uN vd,va,vb` | V | four groups of four byte products summed into 32-bit lanes. See SIMD modifier rules; emulator only. |
| 16 | `vld vd,[a]` | V | load aligned 16 RAM bytes. See SIMD modifier rules; emulator only. |
| 17 | `vst vd,[a]` | V | store aligned 16 RAM bytes. See SIMD modifier rules; emulator only. |
| 18 | `vziplo.uN vd,va,vb` | V | interleave lower halves. See SIMD modifier rules; emulator only. |
| 19 | `vziphi.uN vd,va,vb` | V | interleave upper halves. See SIMD modifier rules; emulator only. |
| 20 | `vunziplo.uN vd,va,vb` | V | collect even lanes from A then B. See SIMD modifier rules; emulator only. |
| 21 | `vunziphi.uN vd,va,vb` | V | collect odd lanes from A then B. See SIMD modifier rules; emulator only. |
## W32

Extended major 7. `op6[25:20] rd4[19:16] ra4[15:12] rb4[11:8] zero8[7:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `addw3 d,a,b` | base | Compute A+B using low32 operands and a 32-bit result; D=sext32(result). |
| 1 | `subw3 d,a,b` | base | Compute A-B using low32 operands and a 32-bit result; D=sext32(result). |
| 2 | `shlw3 d,a,b` | base | Compute A << (B&31) using low32 operands and a 32-bit result; D=sext32(result). |
| 3 | `shrw3 d,a,b` | base | Compute unsigned(A) >> (B&31) using low32 operands and a 32-bit result; D=sext32(result). |
| 4 | `sarw3 d,a,b` | base | Compute signed(A) >> (B&31) using low32 operands and a 32-bit result; D=sext32(result). |
| 5 | `andw3 d,a,b` | base | Compute A&B using low32 operands and a 32-bit result; D=sext32(result). |
| 6 | `orw3 d,a,b` | base | Compute A&#124;B using low32 operands and a 32-bit result; D=sext32(result). |
| 7 | `xorw3 d,a,b` | base | Compute A^B using low32 operands and a 32-bit result; D=sext32(result). |
| 8 | `mulw3 d,a,b` | M | Compute A*B using low32 operands and a 32-bit result; D=sext32(result). |
## MX

Extended major 8. `op4[25:22] data4[21:18] base4[17:14] off14[13:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `ldq d,[base+offset]` | base | D=load64(A). |
| 1 | `stq d,[base+offset]` | base | store64(A,D). |
| 2 | `ldws d,[base+offset]` | base | D=sext(load32(A)). |
| 3 | `ldwu d,[base+offset]` | base | D=zext(load32(A)). |
| 4 | `ldbs d,[base+offset]` | base | D=sext(load8(A)). |
| 5 | `ldhs d,[base+offset]` | base | D=sext(load16(A)). |
## LOOP

Extended major 9. `op2[25:24] counter4[23:20] rel20[19:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `dbnz counter,target` | F | D=D-1 modulo 2^XLEN; if D!=0 nextPC=sequentialPC+2*sext(rel20); D must not be x0. |
## FLOW

Extended major 10. `op4[25:22] data4[21:18] base4[17:14] stride14[13:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `ldpi.b d,[base],stride` | F | Use old base as aligned address; D=zext(load8(address)). Update base by transfer size (compact) or sext(stride14) (extended) only on success; base != x0 and base != data. |
| 1 | `ldpi.h d,[base],stride` | F | Use old base as aligned address; D=zext(load16(address)). Update base by transfer size (compact) or sext(stride14) (extended) only on success; base != x0 and base != data. |
| 2 | `ldpi.w d,[base],stride` | F | Use old base as aligned address; D=zext(load32(address)). Update base by transfer size (compact) or sext(stride14) (extended) only on success; base != x0 and base != data. |
| 3 | `ldpi.q d,[base],stride` | F | Use old base as aligned address; D=zext(load64(address)). Update base by transfer size (compact) or sext(stride14) (extended) only on success; base != x0 and base != data. |
| 4 | `stpi.b d,[base],stride` | F | Use old base as aligned address; store8(address,D). Update base by transfer size (compact) or sext(stride14) (extended) only on success; base != x0 and base != data. |
| 5 | `stpi.h d,[base],stride` | F | Use old base as aligned address; store16(address,D). Update base by transfer size (compact) or sext(stride14) (extended) only on success; base != x0 and base != data. |
| 6 | `stpi.w d,[base],stride` | F | Use old base as aligned address; store32(address,D). Update base by transfer size (compact) or sext(stride14) (extended) only on success; base != x0 and base != data. |
| 7 | `stpi.q d,[base],stride` | F | Use old base as aligned address; store64(address,D). Update base by transfer size (compact) or sext(stride14) (extended) only on success; base != x0 and base != data. |
## BITOPS

Extended major 11. `op6[25:20] rd4[19:16] ra4[15:12] rb4[11:8] zero8[7:0]`

| Opcode | Canonical syntax and disassembly | Extension | Execution |
| ---: | --- | --- | --- |
| 0 | `clz3 d,a` | B | D=clz(A), XLEN for zero. |
| 1 | `ctz3 d,a` | B | D=ctz(A), XLEN for zero. |
| 2 | `popcnt3 d,a` | B | D=popcount(A). |
| 3 | `rev8 d,a` | B | D=reverse byte order of A. |
| 4 | `ror3 d,a,b` | B | D=rotate right A by B&(XLEN-1). |
| 5 | `rol3 d,a,b` | B | D=rotate left A by B&(XLEN-1). |
| 6 | `min3 d,a,b` | B | D=signed minimum(A,B). |
| 7 | `max3 d,a,b` | B | D=signed maximum(A,B). |
| 8 | `minu3 d,a,b` | B | D=unsigned minimum(A,B). |
| 9 | `maxu3 d,a,b` | B | D=unsigned maximum(A,B). |
| 10 | `bset3 d,a,b` | B | D=A &#124; (1 << (B&(XLEN-1))). |
| 11 | `bclr3 d,a,b` | B | D=A & ~(1 << (B&(XLEN-1))). |
| 12 | `binv3 d,a,b` | B | D=A ^ (1 << (B&(XLEN-1))). |
| 13 | `bext3 d,a,b` | B | D=(A >> (B&(XLEN-1))) & 1. |
| 14 | `andn3 d,a,b` | B | D=A & ~B. |
| 15 | `orn3 d,a,b` | B | D=A &#124; ~B. |
| 16 | `xnor3 d,a,b` | B | D=~(A^B). |
| 17 | `sextb3 d,a` | B | D=sext8(low8(A)). |
| 18 | `sexth3 d,a` | B | D=sext16(low16(A)). |
| 19 | `zexth3 d,a` | B | D=zext16(low16(A)). |

Compact F instructions use short R op8 = 23 + the FLOW opcode. Extended majors 12 through 15 and all unallocated subopcodes are reserved.

## MICA-2C additional short R encodings

Only legal in MICA 2.0, with the 2C feature bit enabled. See [MICA2.md](MICA2.md) for full exceptions and writeback rules.

| op8 | Mnemonic | Operand fields | Meaning |
| ---: | --- | --- | --- |
| 31 | `ldsp d,[sp+offset]` | d3, unsigned slot3 | Read XLEN bits at SP + slot * XLEN/8. |
| 32 | `stsp d,[sp+offset]` | d3, unsigned slot3 | Store XLEN bits at SP + slot * XLEN/8. |
| 33..40 | `dbnz.s` | d3, signed halfword displacement6 | Decrement and branch when nonzero; no x0 counter. |
| 41 | `stop` | d3=0, s3=0 | Terminal debug halt until reset. |

MICA 2.0 `wfi` retires then sleeps until a wake event. On the minimal profile, it does not require the T trap extension. `stop` is the explicit debug/terminal halt instruction.
