# Timing status

The only board clock constraint is sys_clk with a 10ns period. No local Vivado
place-and-route or timing closure was executed. Yosys mapping success is not
an Fmax measurement. Simulation cycle counts are not a physical clock rate.

Potential long paths include variable shifts, population counts, operand muxes,
32/64-bit ALU carry, address formation and commit muxes. The split-add experiment
compares mapped resource count and RTL activity; no post-route delay comparison
exists. The Vivado Tcl flow saves setup/hold reports and stops before bitstream
creation on negative slack. Inspect unconstrained paths and DRC as well as
worst slack before a physical demonstration.
