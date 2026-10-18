# Timing analysis

The Arty constraint requests `sys_clk` at a 10 ns period. The board top passes
functional simulation with a 100 MHz input, but Vivado placement, routing and timing
closure are still pending. Yosys reports mapped resources; the simulated cycle
counts describe execution under the selected memory model.

Paths worth inspecting in the first routed design include variable shifts,
population counts, operand selection, ALU carry propagation, address formation and
commit selection. The standalone segmented adder experiment has area and RTL
activity results; its post-route delay comparison is also open.

The supplied Vivado flow saves setup and hold reports and rejects negative slack
before writing a bitstream. Review unconstrained paths and DRC findings along with
worst slack when bringing up the physical board.
