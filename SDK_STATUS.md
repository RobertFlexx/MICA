# MICA 1.0 test and implementation record

Release label: 1.0 SDK. ISA and hardware are experimental. This file is the quick answer to "does it work?"

## Executed here

- All three C++23 programs built successfully with CMake and GCC.
- The Python integration suite passed, including the disassembler and the arena tests (31 Python cases in this release). It assembles source, runs real machine code in the reference interpreter, checks outputs, compares known encodings, checks flow operation encodings, and rejects incorrect operands.
- CRC-32 test vector `123456789` produces `0xcbf43926`.
- Both MICA32 and MICA64 streaming firmware ran in the emulator.
- Drawings were generated from editable Graphviz `.dot` files. Pin constraint locations were checked against Digilent's public master XDC.

## Implemented, but not exercised on physical hardware here

- Multicycle scalar RTL, including F and 32/64-bit scalar operations.
- FPGA SoC (unified byte RAM with asynchronous reads, one UART TX and LED output).
- Arty A7 wrapper and constraint file.
- RTL smoke testbench sources for basic arithmetic and F. No RTL tool was available for successful HDL compile/sim/synthesis in this environment. **The HDL is unverified, and its timing is unknown.**

## Emulated only

- 128-bit packed SIMD execution and single-hart atomics. Both work as reference software models, not as wired datapaths in `rtl/mica_core.sv`.

## Designs only

- Interrupt nesting, memory protection, coherent multicore, synchronized task switching, scalable pipelines, SIMD clock gating, DDR interfaces, PCB/ASIC silicon implementation, and performance/energy leadership.

## Known rough edges

- No linker, ELF output, executable-format metadata or debugger symbols.
- No C/C++ backend and no standards-conformant hosted libc/libstdc++. Freestanding assembly modules are not C-linkable yet.
- The core relies on a combinational read memory interface. That is useful for simple tests, but does not represent a robust block-RAM, AXI or external DRAM controller.
- Memory faults/traps are terminal in the RTL demonstration. `wfi`/`ecall` halt.
- Model-based execution doesn't prove interrupt safety, multicore memory order, synthesis feasibility or power savings.
- Branch target alignment and reserved opcode trapping still need independent formal property checks.

## Release acceptance gates

A version can ship as an experimental SDK when assembler/simulator tests pass and the limitations are named. Physical hardware release requires simulation, lint, formal assertions, synthesis, timing closure, FPGA bring-up, FPGA memory correctness testing, and differential core-versus-interpreter traces. Replacing RISC-V in a product would require a real compiler, stable ABI, memory/privilege model, performance benchmarks, documentation, debug probes and third-party ecosystem.
