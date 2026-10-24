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
