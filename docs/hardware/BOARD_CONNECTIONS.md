# Arty A7-100 connections

Target part: xc7a100tcsg324-1, Arty A7-100 rev D/E. The pin assignments were checked
against [Digilent's master
XDC](https://github.com/Digilent/digilent-xdc/blob/master/Arty-A7-100-Master.xdc) on
2026-10-17. No external wiring is needed for the onboard LEDs or USB UART. Do not
reuse this constraint file for another board or FPGA package.

| RTL port | Package pin | Standard | Connection |
| --- | --- | --- | --- |
| CLK100MHZ | E3 | LVCMOS33 | onboard 100 MHz oscillator, clock domain sys_clk |
| btn_reset | D9 | LVCMOS33 | button0, high when pressed |
| led[0],led[1] | H5,J5 | LVCMOS33 | GPIO latch bits 0, 1 |
| led[2],led[3] | T9,T10 | LVCMOS33 | halted, fault |
| uart_txd | D10 | LVCMOS33 | FPGA TX into onboard USB UART receive path |
| uart_rxd | A9 | LVCMOS33 | host TX into FPGA RX, synchronized in mica_uart_rx |

The table lists UART directions relative to the FPGA. Use
the onboard programming/UART USB connector and the board's documented power
configuration. The FPGA I/O voltage standard is 3.3V; board regulation,
configuration wiring and voltage domains are documented in the board schematic.
Consult [Digilent's Arty A7 reference
page](https://digilent.com/reference/programmable-logic/arty-a7/start) and its
revision-specific schematic before changing external electrical wiring.
