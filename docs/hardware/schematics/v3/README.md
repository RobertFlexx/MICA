# MICA 3.0 development engineering sheets

This new collection documents implemented ISA 2.0-compatible hardware. It is an RTL engineering reference, not a physical electrical schematic. Pipeline/security gaps are status sheets; unsupported circuitry is not drawn. Internal boxes are named functional regions of the monolithic core. Sheet 17 records actual instance ports and elaborated connection bits.

Generate with `python3 scripts/generate_v3_schematics.py`; CI uses `--check`. Net names, widths, module instances, board pins, source hashes and committed previews are checked. Internal region arrows describe RTL signal flow; they are not a gate-level connectivity proof.

| Sheet | Topic | Editable source | SVG | PDF | PNG |
| --- | --- | --- | --- | --- | --- |
| 01 | Complete scalar processor organization | [DOT](01-processor.dot) | [SVG](01-processor.svg) | [PDF](01-processor.pdf) | [PNG](01-processor.png) |
| 02 | Instruction fetch and parcel assembly | [DOT](02-fetch.dot) | [SVG](02-fetch.svg) | [PDF](02-fetch.pdf) | [PNG](02-fetch.png) |
| 03 | Instruction fields, extension guards and control | [DOT](03-decoder.dot) | [SVG](03-decoder.svg) | [PDF](03-decoder.pdf) | [PNG](03-decoder.png) |
| 04 | Scalar register storage and writeback | [DOT](04-register-file.dot) | [SVG](04-register-file.svg) | [PDF](04-register-file.pdf) | [PNG](04-register-file.png) |
| 05 | Arithmetic, logic, shifts and comparison | [DOT](05-alu.dot) | [SVG](05-alu.svg) | [PDF](05-alu.pdf) | [PNG](05-alu.png) |
| 06 | Branches, calls, returns and counted loops | [DOT](06-control-flow.dot) | [SVG](06-control-flow.svg) | [PDF](06-control-flow.pdf) | [PNG](06-control-flow.png) |
| 07 | Transactional load/store and precise pointer updates | [DOT](07-load-store.dot) | [SVG](07-load-store.svg) | [PDF](07-load-store.pdf) | [PNG](07-load-store.png) |
| 08 | CSR permissions, counters and trap state | [DOT](08-csr.dot) | [SVG](08-csr.svg) | [PDF](08-csr.pdf) | [PNG](08-csr.png) |
| 09 | Precise traps, interrupt priority and wakeup | [DOT](09-traps-interrupts.dot) | [SVG](09-traps-interrupts.svg) | [PDF](09-traps-interrupts.pdf) | [PNG](09-traps-interrupts.png) |
| 10 | Minimal multicycle controller | [DOT](10-controller.dot) | [SVG](10-controller.svg) | [PDF](10-controller.pdf) | [PNG](10-controller.png) |
| 11 | Pipeline implementation status | [DOT](11-pipeline-status.dot) | [SVG](11-pipeline-status.svg) | [PDF](11-pipeline-status.pdf) | [PNG](11-pipeline-status.png) |
| 12 | Optional multiplication and software division | [DOT](12-multiply-divide.dot) | [SVG](12-multiply-divide.svg) | [PDF](12-multiply-divide.pdf) | [PNG](12-multiply-divide.png) |
| 13 | Optional bit operations and result selection | [DOT](13-bit-manipulation.dot) | [SVG](13-bit-manipulation.svg) | [PDF](13-bit-manipulation.pdf) | [PNG](13-bit-manipulation.png) |
| 14 | Implemented scalar DSP stream and SIMD status | [DOT](14-scalar-dsp.dot) | [SVG](14-scalar-dsp.svg) | [PDF](14-scalar-dsp.pdf) | [PNG](14-scalar-dsp.png) |
| 15 | Memory routing, ownership and synchronous SRAM | [DOT](15-memory-bus.dot) | [SVG](15-memory-bus.svg) | [PDF](15-memory-bus.pdf) | [PNG](15-memory-bus.png) |
| 16 | Clock, reset, sleep and activity controls | [DOT](16-clock-reset-power.dot) | [SVG](16-clock-reset-power.svg) | [PDF](16-clock-reset-power.pdf) | [PNG](16-clock-reset-power.png) |
| 17 | Complete implemented SoC integration | [DOT](17-soc.dot) | [SVG](17-soc.svg) | [PDF](17-soc.pdf) | [PNG](17-soc.png) |
| 18 | Arty A7-100 board boundary and verified pins | [DOT](18-fpga.dot) | [SVG](18-fpga.svg) | [PDF](18-fpga.pdf) | [PNG](18-fpga.png) |
| 19 | Implemented register parity and watchdog supervision | [DOT](19-reliability.dot) | [SVG](19-reliability.svg) | [PDF](19-reliability.pdf) | [PNG](19-reliability.png) |
| 20 | Security hardware implementation status | [DOT](20-security-status.dot) | [SVG](20-security-status.svg) | [PDF](20-security-status.pdf) | [PNG](20-security-status.png) |

[Validation](validation.json), [RTL widths and ports](rtl-inventory.json), [SoC connection bits](soc-connectivity.json), [verified board map](board-pins.json).

C32, E32 and L64 cores are elaborated independently; displayed core pages use E32 and annotate differing L64 widths. The SoC view enables RX/CRC/watchdog/parity. The real board wrapper retains its actual smaller scalar configuration. No routed timing, physical energy or qualification is implied.
