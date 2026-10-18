# Timing analysis

The Arty XDC specifies a 10 ns `sys_clk` period. Board-top simulation uses a
100 MHz input. Routed timing and maximum clock frequency are unmeasured;
Vivado implementation and physical board tests are pending.

`fpga/scripts/build_arty.tcl` saves setup/hold, utilization and
DRC reports and rejects negative slack before writing a bitstream. Review
unconstrained paths as well. Likely critical paths include variable shifts,
popcount, operand selection, carry propagation, address generation and COMMIT.

The [verification report](../engineering/MICA2_VERIFICATION.md) records functional
simulation and resource mapping. The segmented-adder experiment also requires a
routed delay comparison.
