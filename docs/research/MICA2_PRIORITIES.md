# MICA 2.0 research priorities

The revision now demonstrates compact-loop byte savings against compressed
RISC-V and has local RTL/synthesis evidence. The next step is matched physical
measurement before spending more hardware area. The 1.0 review identified real weak spots. Some are now
fixed in a limited way, others need a compiler or FPGA measurements.

## What changed already

The 2.0 compact branch saves two bytes per iteration compared with the old
four-byte `dbnz`, in a loop small enough for the six-bit displacement. Stack
loads and stores are two bytes in either width. This matters most to MICA-64,
where general eight-byte loads and stores previously took four bytes. In
MICA-32, an existing short `ldw/stw [sp+offset]` can already be two bytes, so
claiming that `ldsp/stsp` halves ordinary 32-bit stack traffic would be wrong.
The new forms instead provide unsigned slot addressing with a clean ABI form.

`adrpc` addresses a real compiler gap, but is only a PC-relative primitive at
present. ELF relocation and linker relaxation are separate unfinished work.
MICA-2L now uses a sign-extended canonical value for a 32-bit `ldw`. The
zero-extending `ldwu` variant still exists. `wfi` is finally wakeable even
on a core without T. The engineering win has to be demonstrated on physical
hardware, not inferred from an opcode mnemonic.

## The uncomfortable parts

**Register pressure.** The tiny core still offers eight register slots, three
of which are zero, SP and LR. The optional 16-register profile should be a
compiler-controlled choice. Get an LLVM backend working, measure spills and
code size on the same C workloads, then decide whether the compact register
encoding should change again. Do not change ABI register numbers casually.

**Register field positions.** Existing 32-bit formats have multiple register
layouts. A truly unified 2.0 format would be a breaking decoder and linker
change. We did not pretend that work was finished. It remains a design study
that must first quantify decoder mux count and critical path.

**Multiply and divide.** Small embedded cores can handle divides in the
runtime. `mulh`, signed/unsigned division, and Q31 accumulator variants need
compiler-generated instruction traces and hardware area estimates before
becoming mandatory. A combinational divider could erase any area win from
compact loops.

**Interrupt response.** The T trap profile does not have priorities, nested
vectored exceptions, tail-chaining or hardware context stacking. Compare
interrupt entry/exit cycles, not just the presence of an `eret` opcode.

**Physical core size.** The earlier Yosys LUT number came from a particular
core/SoC configuration and cannot be compared directly with a vendor's
bare-core figures. Synthesize both cores in a matched FPGA flow, separate out
SRAM, UART, counters and debug, and publish the full scripts.

**64-bit ambition.** A tiny sensor node is rarely improved by 64-bit pointers
and 128-bit SIMD context. Keep MICA-2L and DSP optional until narrow workloads
justify their dynamic and static power costs.

## Real projects worth studying

- [RISC-V compressed spec](https://docs.riscv.org/reference/isa/unpriv/c-st-ext.html): signed/unsigned offsets, SP-relative forms and their restrictions.
- [CORE-V CV32E40P custom extensions](https://docs.openhwgroup.org/projects/cv32e40p-user-manual/en/cv32e40p_v1.7.2/instruction_set_extensions.html): post-increment memory operations, hardware loops, multiply-accumulate and ALU extensions.
- [PicoRV32](https://github.com/YosysHQ/picorv32): size/performance switches, memory handshakes, register-file port choices and FPGA implementation numbers.
- [Arm Cortex-M exception tail-chaining](https://support.arm.com/documentation/107706/0100/Use-case-examples/irq-priority-basic/Case-2--tail-chaining): why back-to-back interrupt service deserves its own measured path.

Borrow the lessons, not the claims. Matching external numbers requires matched
technology, constraints, compiler settings, memories and workloads.

## Three experiments that could make a difference

1. One-write-port register bank with two-cycle F commit. Measure area, CPI and
   whether maintaining precise retirement still works with interrupts.
2. A tiny halfword fetch queue that avoids a second SRAM access on a tight
   branch. Measure actual memory activity and added fetch control logic.
3. Clock-enable isolation for the upper 32 bits in a 64-bit datapath. Measure
   switching activity with the same instruction trace and report any added
   timing delay.

A design that loses one of these comparisons should be simplified, not kept
because it looks sophisticated. Microcontrollers have enough clever mistakes
already.

See the [measured encoding comparison](RISCV_COMPARISON.md) and
[current verification report](../engineering/MICA2_VERIFICATION.md).
