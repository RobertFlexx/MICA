# Inside the processor

This note follows `rtl/mica_core.sv` closely. Anything listed as a future target is not in that file yet.

## Core layout

The current core takes XLEN=32 or 64 and has a sixteen-entry register array. x0 reads as zero and writes to it are discarded. XREG=0 blocks instructions that name x8..x15 in long forms, although the current demonstration RTL still allocates storage for them. A genuinely minimized netlist should reduce the physical register file to eight entries, not just restrict the decoder.

There are four states: FETCH0, FETCH1, EXECUTE and HALTED. FETCH0 reads the first 16-bit instruction parcel. A prefix of `11` goes to FETCH1 for the second parcel, otherwise straight to EXECUTE. EXECUTE uses the decoded operation, reads the register file, computes the next PC, and either writes back to a register, performs a store, or halts. That gives **two state-clock periods** per ordinary 16-bit instruction and **three** per extended instruction in the ideal combinational-memory model. These figures are a state diagram accounting, not measured silicon IPC.

The instruction fetch port has an XLEN address and a 16-bit data response. There is no valid/ready signal, no fetch exception input and no instruction cache. The data port uses an XLEN-wide aligned access, byte strobes, and a combinational read response. Real FPGA block RAM, external SRAM, SDRAM and AXI adapters need request/response sequencing. They cannot simply be attached to this interface if they take more than one cycle.

## Flow execution

The load/store datapath already has a base address, access-size decoder, byte-select shifter and register writeback. For F, the first address is the **unmodified base**. The streaming opcode supplies its width; compact form generates stride equal to width, while extended form supplies a signed byte stride. An illegal combination must fault: base=x0, base=data, unaligned effective address, unsupported XLEN width or unavailable register. The emulator checks all these conditions before memory access.

In the RTL, short flow instructions use R opcodes 23..30 and extended flow is major 10. Loads write two scalar registers in the same execute state: the loaded data destination and the updated base. Stores update only the base register and use the existing bus write path. This makes the execution state carry more register-write mux logic. For real frequency work, measure that path and consider a separate writeback stage rather than assuming fused instructions are free.

`dbnz` is major 9. Its result is the old counter minus one modulo XLEN; the PC-relative target is only selected when the decremented counter is nonzero. The counter is ordinary register state. Traps and future context switches therefore need no special loop-state CSR.

## Why small instructions may help

Fetching two bytes instead of four can reduce instruction memory traffic. Instruction memory is often a meaningful part of embedded energy. But the decoder can become wider because the core supports both lengths, and an eight-register program may need more spills. These are tradeoffs, not automatic wins. MICA's first serious research question is whether the flow form pays back its extra decode and second register write.

The right experiments are at least: GPIO bit toggles, byte and word copies, memory search, small vector dot products, CRC32, branch-heavy dispatch, 64-bit pointer arithmetic, and idle/wakeup duty cycles. Report program bytes, retired instructions, memory reads and writes, clock cycles, netlist utilization, slack, and measured joules. Small instruction count improvements are not enough.

## 32 and 64 bits

XLEN64 doubles the width of registers, the adder, the shifter and most buses. That almost always has a physical cost, even if the instruction is still only 16 bits. MICA64's native `ldq/stq` and W32 operations make mixed pointer/data code possible, but a small 32-bit controller should remain on MICA32 when its workload and address space do not require 64-bit math. Future research can try a segmented 64-bit datapath (two 32-bit beats), accepting extra latency to reduce wide switching capacitance.

The present RTL implements fully wide operations. It does not already have operand isolation, staged shifts, segmented vectors or any clock/power isolation scheme. Those appear only in proposed diagrams.

## Vector implementation options

The ISA specifies eight 128-bit vector registers. The hardware should offer several possible legal implementations:

| V implementation | Physical lane width | Work per instruction | Expected tradeoff |
| --- | ---: | --- | --- |
| Parallel | 128 bits | all lanes together | shortest latency, more simultaneous switching |
| Two-slice | 64 bits | two internal slices | lower datapath width, more cycles |
| Four-slice | 32 bits | four internal slices | modest arithmetic area, higher latency |
| Tiny | 8/16 bits | many internal slices | smallest lane engine, high control overhead |

All should produce identical architectural results. Saturation and per-lane rounding need bit-exact tests. A vector implementation must either save the full 1024-bit state on a task switch or implement a verified and secure lazy-save protocol. The current hardware has **no vector unit**.

## Four problems to solve before multicore

1. Specify a global ordering rule for normal, MMIO and atomic accesses. It cannot be left to bus-arbiter luck.
2. Make every memory operation a transaction with explicit commit, error and retry behavior. Flow pointer updates must not retire on a failed request.
3. Implement a coherent reservation scoreboard for LR/SC and invalidate reservations on every conflicting store, including writes by another hart or DMA.
4. Add a robust trap/interrupt ABI with memory-protection faults, timer tick, per-hart stack and state preservation.

Until then the multi-hart schematic is a design study, not a hardware feature.

## Proposed separate innovations to investigate

**Fused local progress.** Rather than storing a hidden "loop engine" state that must survive interrupts, MICA's F work is expressed through visible registers. This favors preemptible controllers. It should be compared with CORE-V hardware loops and register post-increment architectures. The specific combination may have value, but neither constituent idea is new.

**Energy-graded XLEN64.** Experiment with a two-beat 32-bit physical arithmetic lane for 64-bit cores, while preserving exactly the same visible instructions. This could help low-duty-cycle 64-bit controllers; it might also lose when the workload is truly 64-bit-heavy.

**Quiet SIMD.** Support instruction-level isolation of inactive vector slices and a runtime policy that only powers or clocks vector datapaths when actively used. Real clock gating needs a technology-appropriate integrated gate and clock-tree analysis. A random RTL AND gate on a clock is not acceptable.

**Fetch-byte budget.** Instead of judging the ISA on average instruction length, optimize instruction fetch bytes *per useful operation*. Flow demonstrates a concrete reduction for a common loop. A compiler backend is needed to find out if the advantage survives realistic code generation.
