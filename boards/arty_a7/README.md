# Arty A7 wiring and first build

This is a mapping to parts already present on a Digilent Arty A7 development board. It is not a custom motherboard layout. The chip, regulators, JTAG adapter, clock and LEDs are soldered to the board by the manufacturer.

| MICA top signal | Arty A7 package pin | Connected hardware |
| --- | --- | --- |
| CLK100MHZ | E3 | 100 MHz oscillator |
| btn_reset | D9 | Button 0 |
| led[0] | H5 | Green LED 0: GPIO bit 0 |
| led[1] | J5 | Green LED 1: GPIO bit 1 |
| led[2] | T9 | Green LED 2: CPU halted |
| led[3] | T10 | Green LED 3: instruction fault |
| uart_txd | D10 | FPGA transmit to USB UART bridge |

Use the exact top `mica_arty_a7.sv` with `arty_a7.xdc`, all three RTL sources under `rtl/`, and a generated `program.mem8`. Default program RAM is 4096 bytes so that the asynchronous prototype memory is smaller and more likely to fit as distributed RAM. **This is not a verified timing-closed FPGA design.** Building a bitstream without satisfying setup and hold constraints is not sufficient.

1. Assemble a 32-bit firmware image (`examples/fpga_uart32.mica` or `examples/fpga_blink32.mica`).
2. Convert `.bin` to `.mem8` using `python3 toolchain/bin2mem8.py code.bin program.mem8`.
3. In Vivado select the actual Arty A7 FPGA model and create a project with top `mica_arty_a7`.
4. Add `rtl/mica_core.sv`, `rtl/mica_soc.sv`, `rtl/mica_uart_tx.sv`, this top module, `arty_a7.xdc`, and the data image as a simulation/ROM initialization source.
5. Synthesize and inspect inferred memory, RAM resources, WNS/TNS, all critical paths, and warnings. **Stop on timing failure**. If the design cannot meet 100 MHz, reduce the clock with proper clocking resources or redesign the memory interface. Do not divide the clock in an ordinary flip-flop and treat that net as a normal clock.
6. Program through the onboard JTAG link, press button 0 to reset, and use USB serial 115200 8N1 to observe UART traffic.

The USB cable must supply the board as intended by Digilent. Do not put 5 V onto 3.3 V FPGA GPIO. Do not wire logic signals to the board power rails. Before attaching external circuits, check the Arty schematic, I/O bank voltage, ground reference, output-drive limits and level shifters.

Verified pin source: https://github.com/Digilent/digilent-xdc/blob/master/Arty-A7-100-Master.xdc

## What this board does not implement

There is no DDR controller, proper block-RAM handshake, GPIO input, receive UART, interrupt controller, watchdog, secure boot, or cache-coherent multicore fabric. The included UART is transmit-only. The board pin file cannot substitute for a timing report or logic simulation.
