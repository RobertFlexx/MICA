# Pins from Digilent's Arty-A7-100-Master.xdc rev D/E.
# For Arty A7 boards only. Confirm board and revision first.
# Clock: onboard 100 MHz oscillator. Period is a request, not proven timing.
set_property -dict { PACKAGE_PIN E3 IOSTANDARD LVCMOS33 } [get_ports CLK100MHZ]
create_clock -name sys_clk -period 10.000 [get_ports CLK100MHZ]
# Button 0. Active high, press to reset.
set_property -dict { PACKAGE_PIN D9 IOSTANDARD LVCMOS33 } [get_ports btn_reset]
# Green onboard LEDs. led[2] = halted, led[3] = fault.
set_property -dict { PACKAGE_PIN H5 IOSTANDARD LVCMOS33 } [get_ports {led[0]}]
set_property -dict { PACKAGE_PIN J5 IOSTANDARD LVCMOS33 } [get_ports {led[1]}]
set_property -dict { PACKAGE_PIN T9 IOSTANDARD LVCMOS33 } [get_ports {led[2]}]
set_property -dict { PACKAGE_PIN T10 IOSTANDARD LVCMOS33 } [get_ports {led[3]}]
# UART TX from FPGA to FTDI host RX. Do not confuse with host TX.
set_property -dict { PACKAGE_PIN D10 IOSTANDARD LVCMOS33 } [get_ports uart_txd]
# Host TX through FTDI into FPGA RX, synchronized in mica_uart_rx.
set_property -dict { PACKAGE_PIN A9 IOSTANDARD LVCMOS33 } [get_ports uart_rxd]
