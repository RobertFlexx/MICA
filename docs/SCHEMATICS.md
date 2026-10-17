# Schematics and signal drawings

These diagrams are source-controlled block and connection schematics. Each has a `.dot` source, editable `.svg`, and rendered `.png`. They are intended to follow real RTL signals and help with an FPGA build. They are **not** transistor masks, board fabrication Gerbers, component footprints or a complete KiCad electrical rules checked circuit.

| Drawing | What to read |
| --- | --- |
| `01-core-datapath` | scalar source registers, ALU, branch path, fetch, data bus, FSM |
| `02-encoding` | 16-bit classes, 32-bit extension envelope, F bitfields |
| `03-flow-execution` | pointer update and count branch sequencing, fault caveat |
| `04-soc-bus` | current RAM, UART and LED MMIO address mux |
| `05-controller-fsm` | current FETCH0/FETCH1/EXECUTE/HALTED edges |
| `06-arty-wiring` | real named FPGA ports and board peripherals |
| `07-scalable-roadmap` | future multicore memory system, **not implemented** |
| `08-power-domains` | future power gating and monitoring options, **not implemented** |

Original previous prototype overview drawings remain in this directory for continuity, but the numbered drawings are the 1.0 set.

Generate them with Graphviz:

```sh
dot -Tsvg schematics/01-core-datapath.dot -o schematics/01-core-datapath.svg
dot -Tpng schematics/06-arty-wiring.dot -o schematics/06-arty-wiring.png
```

## RTL interface, exact widths

```
imem_addr_o  [XLEN-1:0]  CPU to instruction memory (byte address)
imem_rdata_i [15:0]      memory to CPU, low halfword first
dmem_addr_o  [XLEN-1:0]  CPU to bus, aligned to XLEN/8 bytes
dmem_wdata_o [XLEN-1:0]  CPU to bus, shifted into byte lanes
dmem_wstrb_o [XLEN/8-1:0] write enables for each byte lane
dmem_re_o                 read request, no wait state modeled
dmem_we_o                 write request, no wait state modeled
dmem_rdata_i [XLEN-1:0]  bus to CPU, selected by byte shift
halt_o, fault_o           stop and fault status
pc_o         [XLEN-1:0]  current PC for debug
debug_a0_o   [XLEN-1:0]  x1 for testbench probes
```

The bus is not AXI, Wishbone or TileLink. It has no ready/valid/error handshake. A synchronous memory, multi-hart arbiter or external peripheral fabric needs an adapter **and a changed core retirement protocol**. Without that, memory operations can silently return old/invalid data.

## FPGA hookup and practical safety

Use `boards/arty_a7/mica_arty_a7.sv` and `boards/arty_a7/arty_a7.xdc`. The wrapper already maps FPGA pins for the 100 MHz oscillator, button reset, onboard LEDs and USB UART. There is no soldering required for this board-level configuration. For custom external sensors use voltage-safe buffers, consult the manufacturer I/O voltage tables, and use a common ground. Never connect a motor or relay coil directly to FPGA pins; use a suitable driver with appropriate transient suppression.

For a custom PCB, you still need the FPGA symbol/footprint, bypass capacitors, voltage regulators and sequencing, configuration flash, crystal/oscillator selection, JTAG connector, ESD protection, power budget, pin bank voltage constraints and an electrically checked board design. None of those board files are created or validated by these logical diagrams.

## Additional 1.0 diagrams

- `09-bit-unit` maps the extended major 11 controls into the optional B ALU, with width selection and writeback.
- `10-trap-control` describes the implemented T trap-state registers and machine-only interrupt path.
- `11-split-slice-proposal` is a proposed 64-bit datapath experiment. This drawing is **not implemented RTL**.
- `12-validation-chain` distinguishes SDK software testing, RTL simulation, synthesis, and measured power.

Each new diagram has `.dot`, `.svg` and `.png` files in `schematics/`. The trap drawing includes `irq_i`, which the Arty top-level currently ties low.
