# Related designs

Signed post-increment loads are established prior art. The
[CORE-V custom extension manual](https://github.com/openhwfoundation/cv32e40p/blob/master/docs/source/instruction_set_extensions.rst)
defines signed byte/halfword loads with pointer updates. The
[Arm assembler reference](https://documentation-service.arm.com/static/5ea689299931941038ded38c)
documents signed loads and post-index addressing. MICA does not claim this
operation is original. Its selected design uses a signed 14-bit byte stride,
rejects a base/destination alias, and commits both writes only after a successful
response. Existing unsigned compact forms retain their encodings.

For one signed halfword stream element, MICA's short `ldh` plus `addi` and its
long `ldpi.sh` both occupy four bytes. The new instruction earns its place by
removing a retired pointer-update instruction, providing a larger stride and
supporting high registers. Thumb-2 already has four-byte post-indexed signed
loads; no code-size win is implied. Ordinary RV32I uses separate load and pointer
addition; compressed and custom extensions change that comparison. The signed
dot-product experiment reports complete kernel setup and actual cycles separately
from the compact counted-branch saving. Full compiler recognition remains open.

Post-increment addressing and counted loops have a long history in embedded
processors. MICA-F expresses them through ordinary registers and branches. CORE-V's
[hardware-loop
manual](https://docs.openhwgroup.org/projects/cv32e40p-user-manual/en/cv32e40p_v1.8.3/corev_hw_loop.html)
describes a different approach, with dedicated loop state and restrictions on loop
bodies. A useful comparison would measure instruction fetches, loop setup, interrupt
context and hardware cost on the same workloads.

[Ibex](https://github.com/lowRISC/ibex),
[PicoRV32](https://github.com/YosysHQ/picorv32) and
[CV32E40P](https://github.com/openhwgroup/cv32e40p) are candidates for independent
baselines. Such a comparison needs matched FPGA technology, memory and peripheral
configurations, constraints, validated outputs and documented build settings. The
current r2 measurements compare MICA implementation variants; an equivalent
external-core comparison is still open.

## MICA 3.0 design review

The following primary references inform the reduced-ISA decisions. They establish
prior art and tradeoffs; none supplies a measured MICA performance advantage.
The retained implementation decisions are in the
[3.0 architecture contract](../architecture/MICA3.md).

| Architecture | Relevant design | MICA decision |
| --- | --- | --- |
| [RISC-V compressed specification, 20260120](https://docs.riscv.org/reference/isa/v20260120/unpriv/c-st-ext.html) | Some compact formats map three-bit fields to x8..x15; stack forms have separate reach | Keep existing low-register mapping for compatibility; use compiler frequencies before any redesign |
| [Arm DUI 0489C, sections 3.3 and 3.9](https://documentation-service.arm.com/static/5ea689299931941038ded38c) | Post-indexed signed loads, stack operations and compact control flow already exist | Retain precise F transactions; do not claim post-increment novelty or infer a whole-program density win |
| [MIPS Technologies MD00086 rev 2.50, original manual mirrored by TUHS](https://minnie.tuhs.org/CompArch/Resources/MD00086-2B-MIPS32BIS-AFP-02.50.pdf) | Explicit register arithmetic, HI/LO multiply state and architectural branch-delay rules illustrate state/exception costs | Keep low products in ordinary GPRs and explicit sequential PCs; no delay-slot contract or hidden multiply state |
| [Microchip AVR instruction summary](https://onlinedocs.microchip.com/oxy/GUID-74578654-4F5F-4B29-9F3C-6C3B1F1DF670-en-US-2/GUID-64F3D141-2594-4755-9103-550108045801.html) | X/Y/Z pointer post-increment supports byte streams | MICA uses ordinary GPR pointers; compact stream traversal is established prior art |
| [Cadence Xtensa ISA summary, Loop Option](https://www.cadence.com/content/dam/cadence-www/global/en_US/documents/tools/silicon-solutions/compute-ip/isa-summary.pdf) | LBEG/LEND/LCOUNT and implicit loop-back reduce branch overhead but add context and restrictions | Retain ordinary counted branches; hidden loop state needs measured fetch/interrupt benefits |
| [Synopsys ARC XY memory design](https://www.synopsys.com/articles/performance-coding-advantages.html) | Dedicated memories, address generators and fused data moves serve larger DSP designs | Keep one explicit scalar transaction; defer parallel memory/DSP machinery from the compact core |

Shared arithmetic resources and operand isolation are ordinary implementation
techniques. MICA's value must come from measured combinations of compact
instructions, precise effects, small configurations and usable tools. Neither
renaming existing operations nor counting opcodes demonstrates independence.
The 3.0 revision allocates no new instruction encoding.
