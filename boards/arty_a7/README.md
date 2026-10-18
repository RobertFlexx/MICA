# Arty A7-100 target

This target uses the Digilent Arty A7-100, part `xc7a100tcsg324-1`, with its
100 MHz oscillator, onboard LEDs and USB UART. The default image uses 4 KiB of
initialized SRAM. `mica_arty_a7.sv` is the board top and `arty_a7.xdc` contains
the checked package-pin assignments.

The [FPGA guide](../../docs/hardware/FPGA_BUILD.md) covers image selection,
Vivado builds and serial-console behavior. [Board connections](../../docs/hardware/BOARD_CONNECTIONS.md)
records pin direction and electrical references. The actual top passes
simulation; physical boot and post-route timing remain to be measured.
