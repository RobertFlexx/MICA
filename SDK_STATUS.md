# MICA 1.0 implementation status

This is an updated 1.0 SDK, not a new ISA major version. Hardware maturity is lower than software maturity.

## Run in this environment

- All C++23 tools compile with GCC: `mica-as`, `mica-dis`, `mica-run`.
- The Python integration suite passes 41 test methods. It runs assembled machine code, B corner cases on both XLEN widths, T exception/interrupt flow, runtime routines, SIMD and atomics in the emulator, plus old regression examples.
- UndefinedBehaviorSanitizer build and integration tests passed during development.
- 10 frozen firmware examples assemble to exactly the same bytes as the previous 1.0 release, checked by `tests/binary_compatibility.py`. Original MICA 1.0 machine code formats were retained. The B extension uses reserved extended major 11. No opcode from an earlier major was reassigned.
- No energy, Fmax, timing closure, or silicon evidence has been produced.

## Implemented in RTL source, not independently verified on FPGA

- XLEN32/64 multicycle scalar, M/X/F parameters from previous SDK.
- New `BITOPS=1` combinational bit-operation datapath.
- New `TRAP=1` ecall/eret and one-level interrupt entry, machine-level CSR state. `irq_i` is exposed and tied low by the current Arty wrapper.
- `features`, `arch` and optionally `instret_lo/hi` with `PERF=1` (off by default to avoid extra switching). Actual cycle counter is not implemented in RTL.
- HDL smoke-test benches and CI targets for B and T are included. The RTL was **not compiled or simulated with an HDL tool during this update**. Success in the software interpreter is not a substitute.

## Not yet implemented

- Precise traps for illegal instructions, misaligned accesses and memory faults. Both minimal RTL and T emulator treat most non-ecall faults as fatal.
- MPU or other memory isolation, privilege levels, a complete interrupt controller or tail chaining.
- Valid/ready memory interface, inferred synchronous BRAM, caches, coherent multicore, DMA arbitration.
- Hardware A and V, production low-power clock gating, synthesis constraints and power measurements.
- Compiler, ELF linker, C ABI/toolchain, standardized libc/libstdc++, standard debugger protocol.

## Next gates

1. Run `make -C rtl sim32 sim64 sim-flow32 sim-flow64 sim-bits32 sim-bits64 sim-trap sim-trap-irq` with a supported SystemVerilog simulator. Fix any RTL syntax or behavior failures before synthesis.
2. Capture instruction retire/writeback traces in RTL and compare with the emulator for randomized generated firmware.
3. Replace asynchronous reads with a synchronized ready/valid memory handshake and validate actual FPGA block RAM inference.
4. Add precise faults and handler behavior before advertising an RTOS-capable CPU.
5. Measure Fmax, area, instruction count and joules per task versus equivalent existing cores.
