# Reproducible benchmarks

`benchmarks/hardware.py` assembles checked arithmetic, copy, string, division and
CRC firmware, compares both fetch configurations against the reference, and reports
retirement, ROM bytes, cycles, IPC and instruction transactions. Five fixed seeds
generate 25% request stalls and 0..8/0..10 response-delay counters for
instruction/data. Median cycles and raw runs are retained. Driver handshake overhead
is part of this defined model. Neither frequency nor energy is inferred from these
cycle counts.

`benchmarks/emulator_mips.py` validates result/retirement on an addi/dbnz loop and
reports median host time plus every repetition. It distinguishes reference, short
fast interpreter and specialized counted-loop translation. The last is not a general
JIT or a realistic whole-program throughput rating. Process launch is included. CPU
identity, OS, repetitions and iteration count accompany results.

The engineering report links archived r2 inputs and results. The EPYC report
records r1 measurements. Matched synthesis and power results for an independent
ISA baseline are not available.

## MICA 2.0 versus RISC-V encoding

`benchmarks/riscv_density.py` measures actual MICA, LLVM RISC-V and Thumb
assembler output. The [comparison](RISCV_COMPARISON.md) records 6-byte MICA copy
bodies versus 12/16-byte compressed RISC-V examples and 12-byte Thumb sequences,
and the stack-access tie.
It measures handwritten body bytes, not complete C applications, RISC-V CPU
execution, routed timing or power. New evidence is archived under
[mica2](../engineering/results/mica2/README.md).
