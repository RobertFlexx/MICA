# Build MICA physically on an FPGA board

## Important boundaries

The included `rtl/*.sv` files are **hardware source for a minimal CPU**, not a PCB ready for manufacture. The `.svg` files are *block-level connection diagrams*, not transistor layouts or detailed EDA netlists. Before making a PCB we need the **exact FPGA/dev-board model, pinout, oscillator frequency, voltage rails, reset scheme, JTAG configuration interface, and memory device choice**. Building a custom ASIC requires foundry technology libraries, standard cells, SRAM macros, place-and-route, timing signoff, DRC/LVS, tapeout and fabrication; not something a schematic or source ZIP can guarantee.

This initial target uses the **programmable logic fabric of a 3.3 V I/O FPGA development board**. The FPGA is the chip physically executing the custom processor; MICA isn't an off-the-shelf CPU you can wire on a breadboard without an FPGA or equivalent programmable logic.

## Bill of materials for a generic dev-board prototype

| Component | Quantity | Notes |
|---|---:|---|
| FPGA development board, with configuration USB/JTAG and clock | 1 | choose a device with comfortable SRAM/LUT headroom; check IO levels |
| USB-to-UART adapter with **3.3 V logic** | 1 | serial TX from FPGA connects to adapter RXD; connect common ground |
| LEDs and board-appropriate current-limiting resistors | 0-8 | LEDs may already be fitted on development board; otherwise calculate current per actual IO voltage and LED forward voltage |
| Reset button with defined level/pull-up | 1 | preferably existing on dev board; active-low reset into FPGA |
| USB connection to host computer and jumper wires | as needed | board provides regulator and clock |
| Oscilloscope/logic analyzer | optional | helps with timing, reset and serial debugging |

**Electrical caution:** do not connect a 5 V TTL signal directly to an FPGA 3.3 V-only I/O. Check board documentation for allowed IO bank voltage/current, voltage tolerance, pull-ups and drive strength. Do not power an FPGA from a random resistor or GPIO pin. If using external LEDs, calculate resistor choice from supply voltage, forward voltage, target LED current and pin-current limits. 330 Ω is a *possible* resistor value on a 3.3 V LED circuit, not a universal recommendation.

## FPGA top-level IO

`rtl/mica_soc.sv`:

| Port | Board hookup | Behavior |
|---|---|---|
| `clk_i` | board oscillator e.g. 12 MHz | Clock, `CLOCK_HZ` param must match |
| `rst_ni` | active-low reset button/conditioned signal | resets CPU/GPIO/UART |
| `uart_tx_o` | 3.3 V USB-UART adapter RXD | 8N1, default 115200 baud |
| `leds_o[7:0]` | eight FPGA board LEDs or current-limited LEDs | driven by memory-mapped write |
| `halted_o` | spare LED/debug pin | core saw stop/illegal instruction |
| `fault_o` | spare LED/debug pin | unsupported opcode, alignment fault, etc. |

Select an actual board, then use its **official master constraint/pin map** to assign these ports to physical IO pins. A verified Arty A7 reference pin map is included under `boards/arty_a7/`. It is specific to that board and cannot be reused as a universal pinout.

## Memory layout and IO map

- `0x00000000` onward: one flat program/data RAM image; code and mutable data share the same byte-addressed array. Default wrapper `RAM_BYTES=65536` (64 KiB); tune only if FPGA has resources.
- `0xffff0000`: **write** low data byte to UART TX (requires prior check of busy register).
- `0xffff0004`: emulator-only host exit; *not* implemented as a physical SoC peripheral in v1.0.
- `0xffff0008`: emulator reads cycle counter; wrapper returns PC instead (NOT identical: debug placeholder, reserved for future proper timer).
- `0xffff000c`: UART busy status, bit0; emulator returns zero since simulated UART is immediate.
- `0xffff0010`: LED latch, low 8 bits on write; emulator saves same for debugging.

Registers are little endian. Loads/stores must be naturally aligned. Peripheral addresses above 4 GiB are not decoded by the example SoC. The bus is a **single-hart, noncached, single-cycle read** toy bus, not AXI/APB/Wishbone and not appropriate for an external asynchronous SRAM without proper timing bridges.

### Generate a program for RTL

```sh
cmake -S . -B build
cmake --build build
build/mica-as --xlen 32 examples/arithmetic32.mica -o program.bin
python3 toolchain/bin2mem8.py program.bin program.mem8
```

The `.mem8` file contains one two-digit hexadecimal byte per line. The `$readmemh` memory array loads a byte per entry. **Intel HEX output is for memory-programmer tooling; do not feed it directly into `$readmemh`**.

### Simulate on a computer if Icarus Verilog is installed

```sh
cd rtl
# Put program.mem8 into this folder first (copy from SDK root).
iverilog -g2012 -s tb_mica -o mica_sim mica_core.sv mica_soc.sv mica_uart_tx.sv tb_mica.sv
vvp mica_sim
# For XLEN=64, assemble arithmetic64.mica, convert to program.mem8,
# then run `make -C rtl sim64` from the SDK root (after placing ROM in rtl/).
```

The smoke test *specifically* asserts the final `a0` value for `arithmetic32.mica` (42), or for `arithmetic64.mica` in XLEN64 mode. Do not load a different example without adapting `tb_mica.sv` expectations. `fpga_uart32.mica` uses the UART and may be too long to complete the whole serialized message under the default 100000 testbench cycles, depending on the selected clock/baud ratio; adjust testbench runtime accordingly. The `fpga_blink32.mica` demonstration is an infinite loop and will intentionally time out if run with this testbench.

**Validation caveat:** Icarus/Verilator/Yosys executables were not available in the current build environment, so RTL syntax, timing and operation **have not been executed or verified here**. Use an HDL simulator and follow up by comparing its instruction trace against `mica-run` before relying on real hardware.

### Synthesize a mapped processor (after RTL lint/simulation succeeds)

With a compatible Yosys/SystemVerilog frontend:

```sh
yosys -p 'read_verilog -sv rtl/mica_core.sv; hierarchy -top mica_core; proc; opt; synth -top mica_core; stat'
```

This is a **generic synthesis experiment** and may require simulator-specific fixes or supported frontend features; it does not program an FPGA. To place-and-route, target a specific FPGA family, memory architecture and constraints (e.g., Yosys + nextpnr on a supported iCE40/ECP5 device). Physical timing constraints, IO standards, programmer cables and JTAG configuration are board-dependent. Validate at the actual target clock, then measure dynamic power with a calibrated board power setup.

## How the hardware operates

`mica_core.sv` uses a fetch/execute **finite-state machine, not a pipeline**. It fetches the first 16-bit halfword; if the prefix is `11`, it fetches the next 16-bit halfword; then decodes/executes the instruction. This requires at least 2 clocks for short instructions and 3 for extended instructions, with no overlapping fetch or data-memory wait states. The fetched instruction drives the integer ALU, register file, branch logic or aligned memory shifter and writes back on the execute clock. The next PC is `PC+2` or `PC+4` unless redirected. `wfi/ecall` halt this demonstration core. A real ISR wakeup implementation is pending.

This implementation intentionally prioritizes clarity and equivalence to the binary encoding. **It is not yet optimized for high clocks or energy efficiency**. The asynchronous multi-read byte-array memory might map to expensive LUT/distributed memory rather than BRAM on some FPGAs. A mature core should migrate to synchronous inferred block RAM with pipeline stalls, explicit clock-enables, compact register-bank organization, CDC handling, real trap state, bus arbitration and validated timing.

## Schematics and diagrams

- `schematics/core.svg` and `.dot`: hardware block/dataflow diagram.
- `schematics/states.svg` and `.dot`: core state-transition diagram.
- `schematics/board.svg` and `.dot`: wiring-level board integration plan.

DOT originals can be edited and re-rendered with Graphviz: `dot -Tsvg schematics/core.dot -o schematics/core.svg`.

## FPGA output power, timing and benchmarking

No fabricated/synthesized gate area, Fmax, current draw or power/energy number is claimed. An accurate experiment should report `cells / LUT / flip-flops / BRAM`, timing slack at declared clock period, work/cycle (including memory traffic), measured µJ/task under representative workloads, and silicon/board conditions. Compare against an RV32E/RV64E implementation at equal memory, clock tree, tool versions and process/family using identical compiled-workload semantics. See `RESEARCH.md`.


## MICA 1.0 Arty A7 target

For a concrete starting point use `boards/arty_a7/mica_arty_a7.sv`, its matching `arty_a7.xdc`, and `boards/arty_a7/program.mem8`. The target maps a 100 MHz clock at E3, button 0 at D9, four onboard LEDs, and transmit UART at D10. The wrapper chooses 4096 bytes of on-chip memory instead of the default 65536 bytes because the current byte-array model has asynchronous reads. Confirm resource inference in Vivado and STOP on timing failure. The input reset is synchronized on release. This is not an assurance of 100 MHz Fmax. For schematics and physical board details, see `SCHEMATICS.md` and the board README.

## B and T prototype datapaths

The `mica_core.sv` parameters `BITOPS=1` and `TRAP=1` enable two more scalar features. B uses a combinational rotate/bit-count datapath; the population-count logic is not pipelined and will need synthesis/timing review before using a high clock. T has `irq_i` (active high) plus software-pending CSR bit0, `status`, `epc`, `cause`, `tvec`, `ie`, and `ip` registers. The SoC exposes the irq port, and the Arty wrapper ties the port low. T does not provide an MPU, automatic register save, or precise memory fault traps. Use the `rtl/tb_bits.sv` and `rtl/tb_trap.sv` testbenches with `make -C rtl sim-bits32`, `sim-bits64`, `sim-trap` and `sim-trap-irq`. The HDL was not simulated in this authoring environment.

The `PERF` core/SoC parameter defaults to 0. Set `PERF=1` to build the 64-bit retirement counter. With `PERF=0`, feature bit7 is zero and the retirement CSRs return zero. This matters for a tiny MCU because an always-incrementing 64-bit counter consumes extra registers and switching.
