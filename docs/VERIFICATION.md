# Verification plan and release gates

There are two kinds of MICA tests: tests that ran here and tests that are still source files waiting for a hardware simulator. Don't mix them up.

## Tests run on this SDK

```sh
cmake -S . -B build -G Ninja
cmake --build build
ctest --test-dir build --output-on-failure
```

`tests/integration.py` checks scalar arithmetic in 32/64 modes, 64-bit literal expansion, vectors, LR/SC invalidation, atomic operations, memory overlap, string and console routines, 32/64 flow, signed strides, register alias rejection, compact encodings, checksum known-answer, macro expansion and malformed-input errors. It launches the actual assembler and emulator as subprocesses.

The emulator is an instruction-set reference. It has no concept of clock period, power dissipation, data-cache miss, speculative issue, branch predictor or bus contention.

## RTL smoke tests, pending execution

`rtl/tb_mica.sv` and `rtl/tb_flow.sv` contain boot tests for arithmetic and flow. The Makefile has named targets for 32-bit, 64-bit and flow simulation, with expected ROM filenames. An external HDL simulator is needed. The source is not counted as a passing test until a simulator compiles it and the waveform/outputs match the reference.

Useful commands on a workstation with Icarus Verilog installed:

```sh
cd rtl
make sim32
make sim64
make sim-flow32
```

Use Verilator lint as a second frontend, then a synthesis tool. Interpret warnings. Treat unintended inferred latches, undriven logic and mismatched array widths as blockers.

## Assertions to add before a taped-out design

1. x0 always reads zero and cannot be written.
2. PC is 2-byte aligned on instruction fetch and branch commit.
3. Every reserved opcode traps. No unsupported feature quietly executes.
4. F base register cannot be x0 or the data register.
5. A failed memory transaction does not change either a streaming base pointer or load destination.
6. Short F load/store advances by exactly the operation width.
7. `dbnz` decrements modulo XLEN before testing branch condition.
8. Only the intended byte lanes assert `dmem_wstrb_o` for each store.
9. Reset initializes the architectural state without unknown control bits.
10. Each 32-bit encoding fetches exactly two halfwords in the correct order.

For the current no-ready, no-error bus, item 5 is not fully satisfiable for external bus failure because the interface lacks an error signal. Fix the interface first.

## Differential testing

Generate an instruction stream that avoids undefined MMIO, self-modifying code and unsupported extensions. Execute it in the emulator and in a cycle-resolved RTL testbench. Compare retired PC, all general registers, every committed store, trap result and XLEN wrapping. Randomize back-to-back F operations, aliased registers as negative tests, signed strides and halfword boundaries. Add an independent reference instruction decoder to avoid copying the same bug into the assembler and simulator.

## Physical measurements

Timing closure must include the actual memory resources and FPGA placement. For energy, report voltage, current sampling method, idle baseline, task duration, repeated test count and standard deviation. Count fetch bytes and bus transfers. Comparisons must use equivalently optimized reference designs with the same amount of memory. A CoreMark score alone cannot establish battery efficiency.
