# Related designs

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
