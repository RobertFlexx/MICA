# Transactional SoC peripherals

All addresses below are byte addresses. Registers accept naturally aligned byte,
halfword or word accesses at the exact listed address. Other addresses, doubleword
accesses and unsupported access directions return a bus error. The core shifts
read/write data into the addressed XLEN bus lane. A request causes effects only on
`valid && ready`; a response remains stable until accepted. Device addresses are
outside SRAM. Do not use atomic instructions on devices.

| Address | Access | Register |
| --- | --- | --- |
| 0xffff0000 | W | UART TX low byte; stalls until transmitter accepts it |
| 0xffff0008 | R | SoC cycle counter low 32 bits, wraps |
| 0xffff000c | R | TX busy bit 0 |
| 0xffff0010 | RW | GPIO output latch low 8 bits |
| 0xffff0014 | R | RX FIFO head low byte; read pops once, empty returns zero |
| 0xffff0018 | R | RX status: bit 0 available, 1 framing error, 2 overrun, 3 present; bits 12:8 byte count |
| 0xffff001c | RW | RX control: bit 0 interrupt enable; write bit 1 clears sticky errors |
| 0xffff0020 | R | Platform capabilities: bit 0 UART RX, bit 1 CRC engine, bit 2 watchdog |
| 0xffff0040 | RW | CRC control: read bit 0 busy; write bit 0 clears/cancels message |
| 0xffff0044 | W | CRC input low byte; stalls while engine busy |
| 0xffff0048 | R | CRC result; request waits for the current byte to complete |
| 0xffff004c | R | CRC completed-byte count modulo 2^32 |
| 0xffff0060 | RW | Watchdog control: enable bit 0, level interrupt enable bit 1 |
| 0xffff0064 | RW | Watchdog minimum interval, reset 0 |
| 0xffff0068 | RW | Watchdog maximum interval, reset 0xffffffff |
| 0xffff006c | W | Watchdog kick; any accepted write is one kick |
| 0xffff0070 | R | Watchdog sticky status: expired bit 0, early kick bit 1 |
| 0xffff0074 | R | Watchdog elapsed clocks, frozen on fault |
| 0xffff0078 | W | Watchdog clear: bit 0 clears elapsed count and both faults |

RX, CRC and watchdog are optional `mica_soc` parameters `UART_RX`, `CRC_ENABLE`
and `WATCHDOG_ENABLE`, all zero
by default. Their absent registers fault; capabilities still reads legally. Reserved
register bits read zero and writes ignore them. GPIO resets to zero; TX is idle
high, RX FIFO empty, interrupt disabled and sticky errors clear. The emulator-only
exit register at 0xffff0004 is not an FPGA peripheral.

## UART receive and interrupts

`mica_uart_rx.v` is plain Verilog-2005. Its two input synchronizer flops carry
`ASYNC_REG` attributes. The divider rounds `CLOCK_HZ / BAUD` to the nearest integer
and must be at least four
clocks per bit. It validates the start midpoint and samples eight bits least
significant first, then checks a high stop bit. A short start glitch produces no
byte. A low stop bit produces a framing pulse and waits for high before recognizing
another start. Reset abandons an incomplete frame.

`mica_sync_fifo.v` stores 16 received bytes in the SoC. It supports arbitrary
positive depth, including non-power-of-two depth and depth one. Payload RAM is not
reset. A full queue can replace its head during a simultaneous pop/push; otherwise a
full RX queue drops the new byte and sets sticky overrun. A new error wins over a
simultaneous control-register clear. There is no flow-control pin. FIFO contents
survive interrupt entry and must be managed by the driver.

Available data and RX interrupt enable produce a level interrupt ORed with the
synchronized external source. Both use `ie[0]` and cause 0x80000001 in MICA32
(0x8000000000000001 in MICA64). Reading one byte need not deassert the interrupt if
more bytes remain. Clearing software `ip[0]` does not acknowledge an asserted
peripheral level. Drain the queue or disable the device interrupt. UART input and
external IRQ each have their own two-flop synchronizer.

## VHDL CRC engine

`mica_crc32.vhd` uses `numeric_std` and an explicit 32-bit unsigned state.
CRC-32/ISO-HDLC uses reflected polynomial 0xedb88320, all-ones initial state and
all-ones final XOR. Bytes enter in software order, bits least significant first. The
empty message produces zero; ASCII `123456789` produces 0xcbf43926. Eight clocks
follow each byte acceptance. The public CRC/count change only after all eight bits
complete; internal working state is not software visible.

`mica_crc_mmio.sv` owns one held response, stalls input/result accesses when needed,
and rejects invalid accesses before effects. Clear takes priority over an unfinished
byte, cancels it and resets CRC/count. Reset cancels all response ownership. The
engine is shared platform state, not automatic task context; drivers must serialize
access or finish each message before switching owners. An interrupt can occur after
an accepted CRC input while the engine finishes.

GHDL executes the native VHDL test. Open-source SoC tests explicitly synthesize it
to Verilog with `ghdl --synth --out=verilog` and simulate the generated module. The
Vivado project reads VHDL natively. Icarus never elaborates VHDL directly.

## Reproduce

Run `make -C rtl sim-peripherals` after building the SDK, or `python3
scripts/test_peripherals.py --tools build`. This runs Verilog-2005 FIFO/UART tests,
a native VHDL CRC test, transactional adapter tests, and both XLEN SoC firmware
tests, simulates the Arty top at 100 MHz with 4 KiB and its UART divider,
then lints the enabled SoC with Verilator. Logs and waveforms are in
`build/peripherals`. `examples/peripherals32.mica` checks CRC, receives `ABC`
through three interrupts and echoes it at the UART pin. For the functional emulator
use `build/mica-as --trap examples/peripherals32.mica -o build/peripherals.bin`,
then `build/mica-run --trap --uart-input 414243 build/peripherals.bin`. A successful
run prints `ABC` and returns x1=42.

The emulator preloads at most 16 explicit hexadecimal input bytes at reset; it does
not sample host serial ports. Its CRC completes immediately and TX busy is zero.
Timing and status-poll instruction counts therefore differ from RTL; functional
results match. This is not a cycle-accurate serial simulation.

The [editable SoC drawing](../../schematics/current/soc-peripherals.dot) and [SVG
preview](../../schematics/current/soc-peripherals.svg) are generated from elaborated
module connections, with a [port
inventory](../../schematics/current/soc-ports.json). Run `python3
scripts/generate_soc_schematic.py --check` to detect stale wiring. The `$` net names
identify Yosys-generated SoC expressions and preserve their source locations.

## Watchdog integration

The VHDL watchdog instantiates `mica_event_counter`. Count starts at zero and
advances once per enabled clock. A kick is valid for `min <= count < max`.
An early kick sets `early`; reaching the maximum without a valid kick sets
`expired`. A zero maximum, reversed window, or maximum lowered below the elapsed
count expires the watchdog. Clear has priority. Disable clears the count but
retains fault flags. Clear/reset is required after a fault. The timeout edge
captures the maximum count; invalid-window diagnostics can capture one elapsed tick.

IRQ is the OR of the two sticky flags, gated by control bit 1. It shares external
cause 1 with UART and the external pin. This is interrupt supervision, not an
automatic reset circuit. Recovery policy belongs to the platform. Min/max narrow
writes zero-extend their value, and reserved control bits are ignored.
GHDL conversion and both XLEN SoC tests exercise the actual VHDL hierarchy.
The emulator enables the model with `--watchdog`; its ticks are execution/sleep
steps, so timer counts are not cycle-accurate hardware results.

## Portable standalone components

`mica_uart_tx_portable.v` is Verilog-2005. The existing SystemVerilog UART is a
compatible wrapper and the SoC uses this engine. Reset aborts a frame and leaves
TX high. `send_i` accepts a byte only while idle; requests while busy are ignored.
TX and RX use the same rounded divisor. TX permits one clock per bit; RX needs four.

`mica_spi_master.v` is a standalone synchronous byte engine, not a mapped SoC
device. Static CPOL/CPHA parameters select modes 0..3. Requests and responses use
ready/valid; the response is held under backpressure. CS stays low for one byte,
MSB first. Each half period is `CLOCK_DIV` clocks. Completion is 17 half periods
after acceptance, including final CS hold time. Reset aborts the transaction,
restores idle clock polarity, clears the response and deasserts CS. There is no
receive synchronizer; external timing must meet the selected SPI clock.
Tests use an independent slave for every byte in every mode and divisors 1, 2, 3.
Bounded formal checks cover ownership, completion and held responses.

`mica_event_counter.vhd` uses `numeric_std`, a positive width and selectable
saturation/wrap. Enable and event must both be high to increment; clear wins and
works while disabled. Overflow is sticky until clear/reset. Inputs are synchronous
to `clk_i`; reset is asynchronous active low. Its integration target is the
watchdog. Native simulation checks saturation, wrap, clear, enable and reset.
Portable Verilog synthesis and GHDL conversion are part of `test_peripherals.py`.
