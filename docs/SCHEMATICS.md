# Schematics and signal drawings

The numbered `.dot` files are the editable source. PNG and SVG output are included. Anything labeled future or not implemented is a design proposal, not secretly finished RTL.

## New in this revision

| Drawing | What it answers |
| --- | --- |
| `13-core-signal-wiring` | What exactly connects to `mica_core`, at which signal widths? |
| `14-memory-contract` | Why can't synchronous FPGA BRAM be wired straight into the existing core? |
| `15-board-electrical-topology` | Where do the clock, reset, UART and LED signals land on an Arty A7? |
| `16-emulator-architecture` | Which accelerated instructions are really supported, and when does execution fall back? |

Diagrams 1 through 12 from the previous SDK remain included for historical comparison.

## Scope

These are FPGA-oriented digital logic and signal connectivity drawings. They are not a complete KiCad electrical schematic, pin-level FPGA symbol, PCB layout, power integrity calculation, or manufacturing package. The Arty A7 already provides regulators, flash, oscillator and JTAG. A custom board must supply those subsystems using the board vendor's reference design and undergo an electrical rules check.

To regenerate a drawing:

```sh
dot -Tsvg schematics/13-core-signal-wiring.dot -o schematics/13-core-signal-wiring.svg
```

The memory drawing flags a particularly expensive mistake to avoid. The new SRAM responds after a clock edge; the existing core assumes data is available immediately. That mismatch must be fixed in control RTL before attempting a BRAM-based deployment.
