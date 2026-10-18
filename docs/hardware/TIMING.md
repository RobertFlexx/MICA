# Timing analysis

The Arty XDC requests a 10 ns `sys_clk` period. The board top is functionally
simulated with a 100 MHz input; **100 MHz is not a timing-closure or Fmax result**.
Vivado placement/routing and physical-board measurements remain pending.

MICA 2.0 now has local Icarus/Verilator simulation and Yosys mapping, recorded
in the [verification report](../engineering/MICA2_VERIFICATION.md).
Those checks supersede the earlier unavailable-tool status. Mapped LUT counts
and memory-model cycle counts do not establish path delay or maximum frequency.

The restored `fpga/scripts/build_arty.tcl` saves setup/hold, utilization and
DRC reports and rejects negative slack before writing a bitstream. Review
unconstrained paths as well. Likely critical paths include variable shifts,
popcount, operand selection, carry propagation, address generation and COMMIT.

The standalone segmented-adder experiment also lacks a routed delay comparison.
No measured clock-speed advantage over RISC-V is claimed.
