# Research plan: make MICA interesting for the right reasons

This is an engineering notebook for MICA 1.0. Nothing in here proves an energy or frequency advantage yet. The goal is to find one that survives a fair baseline.

## What the competition already does well

| Mechanism | Existing reference | What MICA can test |
| --- | --- | --- |
| Compressed 16-bit instructions | RISC-V C and RV32E | Is MICA's base encoding cheaper to decode, or does spilling erase the benefit? |
| Post-increment memory and hardware loops | CORE-V CV32E40P | MICA-F chooses a 16-bit compact stream and one 32-bit counted branch. Does that trade less area for enough code density? |
| Fixed SIMD for microcontrollers | Arm MVE/Helium | Should V use 64-bit, 128-bit, or sliced 32-bit lanes for actual joules/sample? |
| Highly verified small cores | lowRISC Ibex | Can MICA get comparable trace checks, random programs, and formal coverage? |
| Bit manipulation | RISC-V B extension | Can MICA-B fit a tight embedded gate/power budget, or should it stay software? |
| Fast interrupt handling | Arm Cortex-M exception model | Would a more compact entry path beat a software-managed trap when the handler has few live registers? |

Primary technical sources:

- RISC-V embedded base: https://docs.riscv.org/reference/isa/unpriv/rv32e.html
- RISC-V compressed instructions: https://docs.riscv.org/reference/isa/unpriv/c-st-ext.html
- RISC-V bit manipulation: https://docs.riscv.org/reference/isa/unpriv/b-st-ext.html
- CORE-V hardware loops: https://docs.openhwfoundation.org/projects/cv32e40p-user-manual/en/latest/corev_hw_loop.html
- CORE-V PULP extension catalogue: https://docs.openhwfoundation.org/projects/cv32e40p-user-manual/en/latest/corev_instr.html
- Arm M profile and MVE: https://www.arm.com/architecture/cpu/m-profile
- Arm Cortex-M7 exceptions: https://support.arm.com/documentation/ddi0489/b/programmers-model/exceptions?lang=en
- Ibex implementation and benchmarks: https://github.com/lowRISC/ibex
- Ibex co-simulation approach: https://github.com/lowRISC/ibex/blob/master/doc/03_reference/verification.rst

## Proposed experiments not implemented in the 1.0 hardware

### 1. Split-slice 64-bit ALU

Keep a 64-bit architectural value but build the arithmetic datapath as two 32-bit slices. A machine operation can enable the upper slice only when it needs upper input bits, a carry chain, or a 64-bit shift. Every `*w3` instruction computes from the low 32 bits and then sign-extends the final result. If a 64-bit `add3` can generate a carry from bit31, both halves must participate; dropping the carry is incorrect. An optional per-register tag could track upper-half sign-extension, but the tag storage and dependency hazards may cost more power than they save.

**Proposed build:** a reference monolithic ALU and a slice-gated ALU with the same ISA. Count upper-half register reads and toggles in simulation, then synthesize both. Do not compare an ungated one-cycle multiplier to an artificially slowed one.

**Pass condition:** equal architectural traces, equal worst-case load latency, and lower measured energy per task over a varied 64-bit benchmark suite. Record cases where gating increases critical path or LUT count.

### 2. Bounded streaming without hidden memory effects

MICA-F already updates pointers. A more ambitious optional `F2` could track a current pointer and a bound in two architecturally visible registers and fault **before** any memory access that would exceed the bound. Combined with a small count loop, that might reduce separate range-check instructions in sensor streams. It could also increase decode complexity and hurt worst-case execution time. Do **not** add F2 opcodes before specifying what happens on MMIO, cache-line boundaries, partial stores, and interrupts.

**Experiment:** compiler-generated checked memcpy, packet-parser and sensor-buffer loops with and without F2. Compare branch count, code size, access fault precision, LUTs, and critical path. This differs as a combination of explicit stream bounds and pointer updates, not as a claim to have invented pointer checking.

### 3. Peripheral event folding

Some controllers spend more energy waking the CPU than processing an event. A small per-core event FIFO carrying `(source, timestamp, payload)` could batch GPIO/timer notices and let the CPU sleep until a programmable threshold. The timestamp should come from a shared monotonic clock domain and the FIFO should expose overflow. This is a **SoC peripheral proposal**, not an ISA primitive, until bus ordering and wake latency are measured.

**Experiment:** compare raw interrupts, timer batching and the FIFO on bursty input and strict-deadline motor-control cases. Reject batching where missed deadlines are worse than any energy savings.

### 4. Small context-bank experiment

Two switchable banks of x1..x7 could reduce task handoff saves for a pair of real-time loops. The cost is twice the register storage, explicit bank state at exception entry, and possible leakage. Existing register-banking processors are prior art; this is a targeted two-context experiment, not a new concept. Require a complete exception ABI and demonstrate meaningful end-to-end switching energy savings before treating it as an extension.

### 5. Actual SRAM timing and multi-hart order

The current core uses a combinational memory interface and has no proper wait-state protocol. The next hardware milestone is `valid/ready/error` on both instruction and data paths, independent completion, a two-entry store buffer with documented drain conditions, and a single shared-memory coherence model before adding a second hart. For atomic accesses, define linearization points and test LR/SC reservation invalidation under DMA writes as well as other cores.

**Avoid:** declaring multicore support merely because `amoadd` exists in the emulator. RISC-V RVWMO illustrates how much specification is needed to make shared-memory software portable.

## Benchmark plan

Make the baseline an Ibex micro and an Ibex small configuration, followed by a CORE-V configuration with its code-density extensions. Match process/fabric, voltage, SRAM size and timing, synthesis options and input workloads as closely as possible. Since MICA has no compiler backend yet, hand-written assembly comparisons belong in a separate category rather than a headline performance chart.

Measure at least CRC-32, `memcpy` in several lengths, saturating audio, bit-field GPIO, timer service, 64-bit timestamp arithmetic, string search, small NN dot products and context switching. Report code bytes, retired instructions, mean and worst-case cycles/task, achieved Fmax, leakage/idle power, energy/task with confidence intervals and hardware resource counts. Use geometric-mean speed and energy ratios across workloads and publish the failures.

The feature bitmap and `instret` CSR implemented in this release are the first pieces of repeatable instrumentation. `instret` does not measure stalls or joules. The emulator has no trustworthy CPU cycle model. Use RTL traces and externally measured rail power for actual performance claims.
