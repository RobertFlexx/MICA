# Hardware drawing index

The [new 20-sheet collection](schematics/v3/README.md) is the primary hardware
reference for MICA 3.0 development. It covers the implemented scalar CPU, SoC,
board and optional integrity components, with explicit pipeline/security gaps.
Each sheet has editable source and SVG, PNG and PDF output, source-backed width
and instance checks, and a source/preview manifest. Proposed work is kept in the
[experimental section](schematics/experimental/README.md).

Compatibility drawing paths below remain available and generated from current
RTL. Their older titles describe the retained ISA 2.0 contract.

## Drawing sets

| Set | Contents | Generator |
| --- | --- | --- |
| [3.0 numbered sheets](schematics/v3/README.md) | Twenty source-backed implementation/status sheets, actual instance interfaces and verified FPGA pins | `scripts/generate_v3_schematics.py` |
| [2.0 overview](MICA2_IMPLEMENTATION.md) | Six encoding, datapath, stack, WFI, board and profile drawings | `scripts/generate_mica2_diagrams.py` |
| [Core ports](../../schematics/current/core-ports.svg) | Elaborated `mica_core_txn` ports, directions and widths, MICA2=1 | `scripts/generate_schematics.py` |
| [Datapath](../../schematics/current/datapath.svg), [fetch](../../schematics/current/fetch.svg), [memory](../../schematics/current/memory.svg), [traps](../../schematics/current/traps.svg) | Functional regions with actual Yosys net names and widths | `scripts/generate_schematics.py` |
| [SoC peripherals](../../schematics/current/soc-peripherals.svg) | Actual core, SRAM, UART TX/RX, FIFO, CRC bridge and VHDL engine port wiring | `scripts/generate_soc_schematic.py` |
| [Controller](../../schematics/05-controller-fsm.svg), [board](../../schematics/06-arty-wiring.svg), [verification](../../schematics/12-validation-chain.svg) and other existing paths | Nineteen refreshed compatibility paths and research overviews | `scripts/generate_overview_schematics.py` |

`schematics/current/ports.json` and `soc-ports.json` retain machine-readable
port inventories. The SoC drawing joins identical bit vectors; generated `$`
names identify combinational expressions. Repeated clock/reset rails are recorded
in JSON rather than repeated on every arrow.

## Regenerate and check

```sh
python3 scripts/generate_schematics.py
python3 scripts/generate_soc_schematic.py
python3 scripts/generate_mica2_diagrams.py
python3 scripts/generate_overview_schematics.py
python3 scripts/generate_schematics.py --check
python3 scripts/generate_soc_schematic.py --check
python3 scripts/generate_mica2_diagrams.py --check
python3 scripts/generate_overview_schematics.py --check
```

Generate in that order. The final generator fingerprints all three sets,
previews, source inputs and board constraints in
[manifest.json](../../schematics/manifest.json). Its check catches changed source
or preview files, including a stale preview whose DOT still matches.

The drawings describe architecture and connectivity. Board electrical references
and XDC pins are in [board connections](BOARD_CONNECTIONS.md). PCB fabrication
files and transistor netlists are outside the SDK's scope.

The standalone segmented adder remains an experiment in `rtl/mica_add64.sv`;
the main 64-bit core uses the conventional arithmetic path.
