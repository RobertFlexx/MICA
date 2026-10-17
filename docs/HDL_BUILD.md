# HDL blocks and their actual boundaries

The top-level processor is SystemVerilog. The two extra language modules live under `rtl/verilog` and `rtl/vhdl`. They are independent building blocks. The present CPU cannot pause for a synchronous-memory response, so do not replace its asynchronous data RAM with `mica_sram` until the fetch/LSU controller supports wait states.

## Verilog synchronous SRAM

`mica_sram` accepts one request per clock and returns `rsp_valid` and registered `rsp_rdata` at the following rising edge. Its address is a **word index**, not a byte address. `DATA_W` must be 32 or 64 for the intended boards. `req_wstrb` selects byte lanes, little-endian. A write on a word simultaneously read returns the **old** word. Writes apply at the rising edge. After reset, memory content is unspecified until initialized or written. The reset does not clear the array, which helps retain RAM inference.

```sh
make -C rtl sim-sram
```

Future integration requires a state machine that captures the byte address, aligns to a word index, waits for `rsp_valid`, extracts the correct lane, handles errors, and retires the instruction exactly once. Instruction fetch also needs a mechanism for halfwords crossing a word boundary.

## VHDL windowed watchdog

`mica_watchdog` uses a synchronous state counter with asynchronous active-low reset. Enable disables counting when low, but once a sticky early/expired fault is set it persists until reset. A kick earlier than `min_ticks` asserts `early_o`, a timeout at `max_ticks` asserts `expired_o`, and invalid limit programming asserts expiry. Period counters are unsigned, with a generic bit width, and must be clock-domain stable.

```sh
make -C rtl sim-watchdog
```

This is not a hardware reset supervisor. External circuitry or SoC integration must decide whether an expiry interrupts the CPU, triggers a warm reboot or forces a full reset. Do not drive a board's reset pin from an unconstrained combinational watchdog signal.

## Tool support

`iverilog`/`vvp` simulate the Verilog and existing SystemVerilog tests. `ghdl --std=08` simulates the watchdog. `yosys` checks independent SRAM synthesis. A mixed Verilog/VHDL design may require vendor tools or the GHDL-Yosys plugin; vanilla Icarus does not compile VHDL. Keep the blocks independently testable until a mixed-language top-level build is in place.

## Drawings

See schematics 13 through 16 for current core ports, the exact memory timing mismatch, actual Arty A7 pin names, and emulator engine selection. All source drawings are `.dot`, so the diagrams can be changed when RTL changes. A picture without a bus width is a decoration, not a schematic.
