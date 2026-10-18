# Synthesis methodology

`scripts/synthesize.py` maps MICA-C, MICA-E and MICA-64 SoCs using Yosys
`synth_xilinx -family xc7`, a 4096-byte initialized SRAM and common UART TX/GPIO. A fourth MICA-E-peripherals configuration enables RX/FIFO and the GHDL-converted VHDL CRC engine.
C disables PERF; E/64 enable PERF/T/M/F/B and 64 adds X. Debug trace outputs are
unconnected in the SoC and may be removed. Full logs and JSON primitive counts
are written under `build/synthesis`. Archived measurements are linked from
the engineering implementation report. These are mapped resources, not placed
area, timing, leakage or energy results. The board part is not a process library.

The memory is a true synchronous word array with byte write enables. Fetch
registers the entire RAM word **before** halfword/32-bit selection, allowing
Yosys to merge memory read registers and infer block RAM. Temporary byte-array
initialization was rejected because it caused excessive frontend work. Word
initialization with padded files avoids that expansion. The standalone 64KiB
32-bit RAM experiment maps to 16 RAMB36E1 and passes `check`.

Optional logic must be explicitly excluded at constant parameter boundaries.
Guarding only the final illegal flag did not reliably remove unused multiply,
B or CSR datapaths; r2 explicitly isolates those data expressions. Per-profile
resource reports are required before assuming a small source core is small
hardware. No comparison against independently synthesized Ibex/PicoRV32/CORE-V
configurations has been completed.
