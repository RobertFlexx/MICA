# Arty A7-100 build and bring-up

Build tools and firmware first using BUILDING.md. The board defaults to 4096
bytes of initialized synchronous SRAM, XLEN32, F, T and PERF. Code boots from
address0 in this initialized code/data RAM. A distinct write-protected boot ROM
is not implemented. `examples/selftest32.mica` fits this image and exercises
RAM, arithmetic, feature discovery, timer interrupt, GPIO and UART TX.

```sh
python3 scripts/build_firmware.py --tools build
vivado -mode batch -source fpga/scripts/build_arty.tcl
```

The Tcl flow chooses xc7a100tcsg324-1, loads the board constraints and generated
word initialization file, reads SystemVerilog, Verilog and VHDL natively, synthesizes, places and routes, saves checkpoints and writes
resource/timing/DRC reports under `build/fpga`. It rejects negative setup/hold
slack before writing a bitstream. Vivado was unavailable locally, so this Tcl
flow is supplied **pending execution**. Yosys mapping and SoC simulation are
separate measured results and do not establish Vivado timing closure.

Use Vivado Hardware Manager to connect the actual Arty board and program
`build/fpga/mica_arty.bit` after reviewing reports. No programming action was
performed in this environment. Open the serial port at 115200 baud,8 data bits,
no parity,1 stop bit, no flow control. Press button0 to reset. Expected serial
text is `MICA 1.0 OK` followed by newline; GPIO LEDs0/1 light and halted LED2
lights. Fault LED3 must stay off. The build enables UART RX and CRC, though the default self-test does not consume RX data. To exercise receive, run the Tcl command with `-tclargs peripherals32` and send `ABC`; the firmware echoes it and halts with x1=42.

Icarus `make -C rtl sim-firmware` checks real serialized UART bytes, LED value,
timer entry/eret and successful architectural exit. `sim-scheduler` tests the
64KiB two-task example; its hardcoded task stacks do not fit the 4KiB board
configuration. Physical boot, power consumption and board timing remain
unverified until actual board measurements are recorded.

`sim-peripherals` also simulates the actual `mica_arty_a7` top with 100 MHz,
4 KiB initialized SRAM, RX/CRC enabled and the integer 115200-baud divider.
It checks two-edge reset release, timer-handler completion, GPIO/halt/fault LEDs
and the serialized self-test text. This board-top simulation is distinct from
Vivado implementation, timing closure and physical-board validation.
