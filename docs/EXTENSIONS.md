# B and T: optional MICA 1.0 profiles

Both extensions fit in the 1.0 encoding space. Existing scalar, vector and flow instruction encodings are unchanged. A machine without an extension must reject its instructions. The assembler requires `--bitops` for B. The emulator requires `--trap` for T. Existing `ecall` and `eret` encodings are reused by T.

## B. Bits and bounded instruction traffic

Extended major `11`, payload `op6 rd4 ra4 rb4 zero8`. All fields are bit positions in the 26-bit extended payload. All arithmetic uses the selected XLEN (32 or 64). Every result is truncated to XLEN. Every byte reversal reverses XLEN/8 bytes.

| Opcode | Instruction | Operation |
| ---: | --- | --- |
| 0 | `clz3 d,a` | leading zero bits; zero input gives XLEN |
| 1 | `ctz3 d,a` | trailing zero bits; zero input gives XLEN |
| 2 | `popcnt3 d,a` | count set bits |
| 3 | `rev8 d,a` | reverse order of bytes in XLEN |
| 4,5 | `ror3 d,a,b`, `rol3 d,a,b` | rotate by `b & (XLEN-1)` |
| 6,7 | `min3`, `max3` | two's-complement signed min/max |
| 8,9 | `minu3`, `maxu3` | unsigned min/max |
| 10,11,12 | `bset3`, `bclr3`, `binv3` | set, clear or invert bit `b & (XLEN-1)` |
| 13 | `bext3` | extract selected bit as 0 or 1 |
| 14,15,16 | `andn3`, `orn3`, `xnor3` | `a & ~b`, `a | ~b`, `~(a ^ b)` |
| 17 | `sextb3 d,a` | sign-extend input bit 7 |
| 18 | `sexth3 d,a` | sign-extend input bit 15 |
| 19 | `zexth3 d,a` | zero-extend 16 low bits |

Unary instructions (0..3, 17..19) require `rb=0`. Every opcode requires payload bits 7:0 = zero. Unknown opcodes and wrong reserved bits must fault. The assembler can encode the X register set if `--xreg` is also enabled. Disassembly does not itself prove the target processor supports the extension.

These functions are common prior art, notably in RISC-V bit-manipulation extensions. B is not claimed as a novel invention. The experiment is whether a small, explicitly optional implementation improves full-task energy on MICA, or just consumes FPGA lookup tables for modest throughput gains.

## T. Machine-level exceptions and interrupts

T is a deliberately small trap mechanism for bare-metal control loops and early RTOS work. There is **no user mode, address-space isolation, memory protection, or automatic stack frame**. Firmware saves any registers it wants to keep. The RTL exposes an external `irq_i` level input. The current Arty A7 wrapper ties it low. The emulator can trigger the same path by setting the software pending bit.

Machine CSRs:

| Number | Name | Rights with T | Meaning |
| ---: | --- | --- | --- |
| 0 | `coreid` | R | current core ID, zero in single-core SDK |
| 1 | `status` | R, IE bit writable | bit0=IE, bit1=previous IE, bit2=in handler |
| 2 | `epc` | R/W | saved resume address |
| 3 | `cause` | R/W | trap reason |
| 4 | `tvec` | R/W | aligned, nonzero handler PC |
| 5 | `ie` | R/W | bit0 enables interrupt source 0 |
| 6 | `ip` | R/W | bit0 software-pending source 0; RTL read ORs the external irq level |
| 7,8 | `cycle_lo`, `cycle_hi` | R | emulator step counter. RTL placeholder zero. **Do not use for cycle benchmarks.** |
| 15 | `features` | R | capability bitmap below |
| 16 | `arch` | R | XLEN as an integer |
| 17,18 | `instret_lo`, `instret_hi` | R | retired instruction count, low/high 32 bits, if implemented |

`features`: bit0 XREG, bit1 multiply, bit2 flow, bit3 atomics, bit4 SIMD, bit5 bit operations, bit6 trap handling, bit7 hardware retire-counter availability. The emulator always sets bit7; the scalar RTL sets it only when `PERF=1`. On the example scalar RTL, bits 3 and 4 are zero because that core does not implement A or V. Feature reads do not promise any specific operating frequency.

### Entry

`ecall` with T and a valid `tvec` saves **the next instruction's PC** in `epc`, writes `cause=11`, saves IE into previous IE, clears IE and marks handler active. PC becomes `tvec`. This convention allows a plain `eret` to resume after the call, with no instruction-length parsing in the handler. Without T, `ecall` continues to act as a stop instruction in the SDK's legacy single-program environment.

A source-0 interrupt is taken at an instruction boundary when `(status.IE & ie.bit0 & ip.bit0)` is true. External `irq_i` contributes to `ip.bit0` in RTL. `epc` saves the PC of the instruction that has **not yet** executed. `cause` has bit `XLEN-1` set and low bits equal to `1`. The handler should clear a software pending bit or acknowledge the external device before returning. Otherwise the interrupt repeats.

`eret` requires an active handler. It restores PC from `epc` and IE from previous IE, clears the active flag and previous IE. A second trap while in a handler is not supported by this profile. The reference emulator diagnoses a double trap; the minimal RTL treats a nested `ecall` as illegal. Hardware faults such as an invalid memory address and illegal instructions are still terminal and **not routed through T**. This is why T is not a full privilege architecture.

### Example

```asm
.arch mica32
li32 x1,handler
csrw tvec,x1
li8 x3,7
ecall
addi x3,1
wfi
handler:
  addi x3,10
  eret
```

Run with `mica-run --trap`. The result is x3 = 18. See `examples/trap_irq32.mica` for software-pending interrupt entry.

## Interrupt handler ABI

Handlers do not use the ordinary subroutine ABI. If a handler modifies a register it must save and restore it unless that register is part of its documented handoff. In particular, `x6` is not saved by trap hardware; avoid a nested call unless `lr` is saved first. A stack switch is software's responsibility. Save vector state if a thread uses V and a handler would touch V.

## Compatibility and fault behavior

B and T are opt-in. The assembler emits the same bytes for all preexisting MICA 1.0 instructions. `csrr features`, `csrr arch` and `csrr instret_lo` are available without optional flags. Write attempts to those read-only CSRs are rejected by the emulator. The RTL supports read-only capability and optional `PERF=1` retirement counters, plus T CSR read/write when `TRAP=1`. It does not implement the full CSR address map from the emulator.
