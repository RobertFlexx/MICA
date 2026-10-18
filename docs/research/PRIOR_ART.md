# Prior art and comparison boundaries

MICA F combines visible-register post-increment operations and counted branches.
Neither idea is novel merely because its mnemonic differs. CORE-V's
[hardware-loop manual](https://docs.openhwgroup.org/projects/cv32e40p-user-manual/en/cv32e40p_v1.8.3/corev_hw_loop.html)
describes separate loop state and constraints. MICA currently avoids hidden
loop state; an actual loop-controller implementation and a fair benchmark are
still needed to compare their tradeoffs. No external RTL was copied for r2.

[Ibex](https://github.com/lowRISC/ibex),
[PicoRV32](https://github.com/YosysHQ/picorv32) and
[CV32E40P](https://github.com/openhwgroup/cv32e40p) are candidate independent
baselines. No performance, area or energy superiority is claimed. Comparable
experiments need the same FPGA family, SRAM/peripherals, constraints, validated
workload outputs and documented compiler/tool settings. Emulator wall time and
physical hardware clocks are different measurements.
