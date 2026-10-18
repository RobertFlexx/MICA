# Arty A7-100 build and bring-up

The target is a Digilent Arty A7-100, part `xc7a100tcsg324-1`. The board wrapper
uses XLEN32, F, T and PERF with 4 KiB of initialized synchronous SRAM. Code starts
at address 0 in shared code/data RAM. The image exercises RAM, arithmetic, feature
discovery, a timer interrupt, GPIO and UART transmit.

## Build an image

Build the SDK as described in [BUILDING.md](../../BUILDING.md), then run:

```sh
python3 scripts/build_firmware.py --tools build
vivado -mode batch -source fpga/scripts/build_arty.tcl
```

The Tcl project reads SystemVerilog, Verilog and VHDL, the checked
[constraints](../../boards/arty_a7/arty_a7.xdc), and a padded word initialization
file. It enables UART RX and CRC, runs synthesis, placement and routing, then writes
checkpoints and utilization/timing/DRC reports under `build/fpga`. Negative setup or
hold slack stops bitstream creation.

Vivado execution and timing closure are pending. The local evidence consists of
open-source simulation and Yosys mapping. Those stages are recorded separately in
the [r2 report](../engineering/IMPLEMENTATION_REPORT.md).

## Console and expected behavior

After a successful implementation and report review, program
`build/fpga/mica_arty.bit` through Vivado Hardware Manager. Use the board's onboard
programming/UART USB connection with 115200 baud, 8 data bits, no parity, one stop
bit and no flow control. Press button 0 to reset.

The self-test prints `MICA 1.0 OK` and a newline. GPIO LEDs 0/1 and halted LED 2
light; fault LED 3 stays off. For receive testing, select the other board image:

```sh
vivado -mode batch -source fpga/scripts/build_arty.tcl -tclargs peripherals32
```

Send `ABC`. That program checks CRC-32, receives three bytes through interrupts,
echoes them and halts with x1=42. The [peripheral guide](PERIPHERALS.md) defines the
register map and receive-error behavior.

## Simulation coverage

`make -C rtl sim-firmware` checks UART bytes, GPIO, timer entry/return and the
successful result. `sim-peripherals` also runs the actual `mica_arty_a7` top with a
100 MHz input, 4 KiB SRAM, RX/CRC enabled and the integer UART divider. It checks
two-clock reset release, the timer handler, all four LEDs and serialized self-test
text.

`sim-scheduler` uses the separate 64 KiB two-task configuration; its stacks do not
fit the board's 4 KiB image. A separate write-protected boot ROM is also outside the
current design. Physical boot, board timing and power remain to be verified on
hardware. [Board connections](BOARD_CONNECTIONS.md) records the package pins and
electrical references needed for that work.
