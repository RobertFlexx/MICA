# MICA 2.0 research priorities

MICA 2.0 has measured compact-loop code sizes, RTL simulation results and
synthesis reports. Priorities are compiler support, reference-core area and
physical FPGA measurements.

## Implemented changes

The two-byte `dbnz.s` replaces the four-byte `dbnz` when the target fits its
six-bit displacement. `ldsp/stsp` use two bytes at either XLEN. This reduces
MICA-64 stack-access encoding size from four bytes to two. MICA-32 already has
two-byte SP-relative `ldw/stw`; the new forms add unsigned slot addressing.

`adrpc` provides PC-relative address arithmetic and the `ADRPC16` ELF relocation.
Compact counted branches now have `PCREL6` relocations, and the linker preserves
object alignment. General linker relaxation, independent sections and a compiler
backend remain unfinished. MICA-2L sign-extends `ldw`; `ldwu` zero-extends.
In 2.0 mode, `wfi` supports external wake without T.

## Design priorities

**Register pressure.** MICA-2C has eight register slots, including zero, SP and
LR. Evaluate the optional 16-register profiles using compiler-generated code,
spill counts and matched workloads before revising register encodings or the ABI.

**Register field positions.** The 32-bit formats use several register layouts.
Unifying them would break binary compatibility and require decoder and linker
changes. Evaluate decoder mux count and critical-path delay before proposing
a replacement format.

**Multiply and divide.** Division currently uses runtime routines. Evaluate
`mulh`, signed/unsigned division and Q31 accumulator variants using generated
instruction traces, area estimates and execution time. Divider cost is
particularly relevant to the minimum profile.

**Interrupt response.** The T trap profile does not have priorities, nested
vectored exceptions, tail-chaining or hardware context stacking. Measure
interrupt entry, exit and successive-handler latency under defined bus delays.

**Physical core size.** The earlier Yosys LUT number came from a particular
core/SoC configuration. Compare cores in a matched FPGA flow, reporting SRAM,
UART, counters and debug resources separately from the CPU.

**Optional profiles.** Evaluate the pointer, context-storage and power costs of
MICA-2L and DSP on workloads that require them. Both remain optional.

## Reference designs

- [RISC-V compressed spec](https://docs.riscv.org/reference/isa/unpriv/c-st-ext.html): signed/unsigned offsets, SP-relative forms and their restrictions.
- [CORE-V CV32E40P custom extensions](https://docs.openhwgroup.org/projects/cv32e40p-user-manual/en/cv32e40p_v1.7.2/instruction_set_extensions.html): post-increment memory operations, hardware loops, multiply-accumulate and ALU extensions.
- [PicoRV32](https://github.com/YosysHQ/picorv32): size/performance switches, memory handshakes, register-file port choices and FPGA implementation numbers.
- [Arm Cortex-M exception tail-chaining](https://support.arm.com/documentation/107706/0100/Use-case-examples/irq-priority-basic/Case-2--tail-chaining): successive interrupt handling.

External comparisons require matched technology, constraints, compiler settings,
memory configurations and workloads.

## Proposed experiments

1. One-write-port register bank with two-cycle F commit. Measure area, CPI and
   whether maintaining precise retirement still works with interrupts.
2. A halfword fetch queue that avoids a second SRAM access on short loops.
   Measure memory activity and added fetch-control logic.
3. Clock-enable isolation for the upper 32 bits in a 64-bit datapath. Measure
   switching activity with the same instruction trace and report any added
   timing delay.

See the [measured encoding comparison](RISCV_COMPARISON.md) and
[verification report](../engineering/MICA2_VERIFICATION.md).
