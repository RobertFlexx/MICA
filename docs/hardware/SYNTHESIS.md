# Synthesis

`scripts/synthesize.py` maps nine SoC configurations through Yosys `synth_xilinx
-family xc7`, using 4 KiB initialized SRAM and UART TX/GPIO. The peripheral
configuration adds UART RX/FIFO and the GHDL-converted VHDL CRC engine. Debug trace
outputs are unconnected and can be removed by synthesis.

The [3.0 development report](../engineering/MICA3_DEVELOPMENT.md) records current
matched resource changes. The optional multiplier now shares the scalar read
muxes and zeros inactive inputs; MUL=0 removes the constant-zero product.
Earlier tables below retain their dated ISA 1.0/2.0 scope.

Historical MICA 1.0 r2 results (not current 2.0 measurements):

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

## Earlier MICA 2.0 run

The earlier 2.0 mapped counts are:

| Configuration | Registers | PERF | LUTs | Flip-flops | DSP48 | RAMB36 |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| MICA-C | 8 | off | 4,707 | 980 | 0 | 1 |
| MICA-E | 8 | on | 6,250 | 1,508 | 6 | 1 |
| MICA-64 | 16 | on | 14,742 | 2,885 | 23 | 2 |
| MICA-E-peripherals | 8 | on | 6,617 | 1,823 | 6 | 1 |
| MICA-2C | 8 | off | 4,758 | 982 | 0 | 1 |
| MICA-2E | 16 | on | 7,333 | 1,766 | 6 | 1 |
| MICA-2L | 16 | on | 14,932 | 2,887 | 23 | 2 |

Raw primitive counts are published with the
[2.0 synthesis evidence](../engineering/results/mica2/synthesis/results.json).
MICA-C and MICA-2C both disable PERF for the direct minimal-profile comparison.
MICA-E retains eight slots; MICA-2E has sixteen, so their difference includes
register-bank expansion as well as the 2.0 decode. MICA-64 and MICA-2L have
sixteen slots. All mappings include the same 4 KiB RAM and TX/GPIO; only the
explicit peripherals configuration adds RX/FIFO and CRC.

In this matched minimal-SoC mapping, enabling 2.0 adds **51 LUTs (1.1%) and
2 flip-flops** over MICA-C for compact decode and wakeable WFI.
Routed timing, electrical power and cross-ISA resource comparisons are pending.
