# Synthesis

`scripts/synthesize.py` maps four SoC configurations through Yosys `synth_xilinx
-family xc7`, using 4 KiB initialized SRAM and UART TX/GPIO. The peripheral
configuration adds UART RX/FIFO and the GHDL-converted VHDL CRC engine. Debug trace
outputs are unconnected and can be removed by synthesis.

| Configuration | LUTs | Flip-flops | DSP48 | RAMB36 |
| --- | ---: | ---: | ---: | ---: |
| MICA-C, PERF disabled | 4,499 | 983 | 0 | 1 |
| MICA-E | 6,198 | 1,508 | 6 | 1 |
| MICA-64 | 14,782 | 2,885 | 23 | 2 |
| MICA-E with RX/FIFO and CRC | 6,580 | 1,823 | 6 | 1 |

E and 64 enable PERF/T/M/F/B; 64 also adds X. Complete logs and JSON counts are
written to `build/synthesis`, with the [r2
results](../engineering/results/synthesis/results.json) archived in the repository.
Placement, routing, timing and power are subsequent stages; these counts describe
mapped resources.

## RAM inference

The SRAM is a synchronous word array with byte write enables. Fetch registers the
entire RAM word before halfword/32-bit selection, allowing Yosys to merge read
registers into block RAM. Word initialization files are padded to the configured
memory size. A standalone 64 KiB, 32-bit instance maps to 16 RAMB36E1 blocks and
passes `check`.

An earlier byte-array initialization approach caused excessive frontend work.
Selecting the fetch portion before the RAM read register also obstructed BRAM
inference. Keeping the word register at the memory boundary resolves both
integration and inference concerns.

## Optional datapaths

Disabled operations need constant parameter guards around their data expressions.
Guarding only the final illegal-instruction flag had retained unused multiplier,
bit-operation and CSR logic. The profile mapping reports make that cost visible.
Equivalent Ibex, PicoRV32 and CORE-V configurations have not yet been synthesized in
this flow.
