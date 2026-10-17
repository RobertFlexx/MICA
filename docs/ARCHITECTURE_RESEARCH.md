# MICA, after the easy optimizations

The obvious wins have competitors. Compressed opcodes are not new. Post-increment addressing is not new. Counted hardware loops are not new. Bit manipulation and fixed-width SIMD are not new. If MICA earns a place in a commercial controller, it will be because the complete CPU and surrounding system are cheaper or more useful at a target workload, not because a mnemonic looks impressive.

## Experiment 1: activity-aware XLEN64

Proposal: divide the 64-bit integer arithmetic datapath into independently controlled lower and upper 32-bit computation cones. An explicit W32 instruction never needs the upper 32-bit ALU for its calculation, but register writeback must sign extend as specified. The feature should be controlled by operand dependency and opcode, not by guessing a value's width. Clock gating is easy to get wrong; first experiment with operand isolation, then test inferred clock enables at register boundaries.

Acceptance gate: compare two post-layout XLEN64 cores, one baseline and one with operand isolation, on a controlled distribution of 32-bit and 64-bit operations. Require lower **energy per task** at similar Fmax, no increased critical path in XLEN64 add, and bit-exact traces. Reject the proposal if the control overhead negates the switching reduction.

## Experiment 2: instruction fetch as a first-class energy consumer

Proposal: a 32-bit flash word buffer with halfword steering and a single verified fall-through address. It should only request new flash words on halfword boundary crossing, control-flow redirection, or explicit synchronization. Branches need careful invalidation. This is an ordinary small buffer with a very deliberate cost model, not a speculative cache hierarchy.

Acceptance gate: count physical flash/SRAM fetch transactions per 1,000 retired instructions across control-heavy firmware. Compare with the same memory latency and no buffer. Record branch penalty, gate count, leakage, and idle current. No claim of advantage based only on firmware image bytes.

## Experiment 3: deadline-aware event batching

Proposal: a bounded peripheral event queue controlled by a `max_delay` and `max_events` contract. A sleeping controller can wait for N sensor events or the earliest deadline, whichever occurs first. Mandatory always-on interrupt sources bypass the queue. An instruction or CSR controls policy, but the microcontroller's power controller implements the queue. There is nothing magical about the ISA here.

Acceptance gate: fewer wakeups at equal sensor input rate, no missed hard deadlines, no unsafe starvation of safety events, and lower board-level energy measured at the regulator input. Event queue state must survive clock-domain crossings, resets and interrupt masking with documented semantics. The current MICA RTL implements none of this.

## Experiment 4: fast context switching without 128-bit state tax

Proposal: two small scalar register banks, with user-selectable X extension, and a dirty bit on SIMD state. Interrupt entry could select an emergency bank to reduce the number of stores before servicing a high-priority event. Bank switching must save the return context and cannot hide other tasks' private vector contents.

Acceptance gate: worst-case interrupt response under bus contention, area and idle leakage overhead of the second bank, RTOS task-switch cycles, and coverage for nested interrupts. The present MICA-T model does not have user mode, an MPU or multiple register banks. This remains a research direction.

## Experiment 5: a deliberately limited, predictable core

A high-end profile shouldn't force its cost on the tiny profile. Build a reproducible set of 32-bit cores: C-only, C+M, C+F, C+B, C+F+B, and then an RTOS-capable core once precise faults and privilege are real. Produce a table of per-extension area and switching costs. Sometimes a smaller, slower CPU is the better product if it completes its sensor task and returns to sleep sooner.

## Benchmark rules

The reference competition is real: lowRISC Ibex, PicoRV32 and CORE-V CV32E40P, plus a representative Arm Cortex-M part when available. Use the same technology and program behavior where possible. If a competitor includes a feature MICA doesn't have, publish that difference instead of silently disabling it. Include flash wait states, UART bursts, DMA contention, interrupts, real MCU sleep transitions and compiler quality.

There may be freedom-to-operate and patent questions around any of these ideas. Prior-art review is required before claiming that a design is independent or patentable. MICA's own instruction encodings are independent, but concepts and implementation techniques overlap with earlier work.

References: [Ibex](https://github.com/lowRISC/ibex), [PicoRV32](https://github.com/YosysHQ/picorv32), [CORE-V CV32E40P](https://github.com/openhwfoundation/cv32e40p), [GHDL synthesis](https://ghdl.github.io/ghdl/using/Synthesis.html).
