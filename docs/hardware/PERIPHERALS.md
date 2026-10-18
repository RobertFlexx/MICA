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
| 0xffff0020 | R | Platform capabilities: bit 0 UART RX, bit 1 CRC engine |
| 0xffff0040 | RW | CRC control: read bit 0 busy; write bit 0 clears/cancels message |
| 0xffff0044 | W | CRC input low byte; stalls while engine busy |
| 0xffff0048 | R | CRC result; request waits for the current byte to complete |
| 0xffff004c | R | CRC completed-byte count modulo 2^32 |

RX and CRC are optional `mica_soc` parameters `UART_RX` and `CRC_ENABLE`, both zero
by default. Their absent registers fault; capabilities still reads legally. Reserved
register bits read zero and writes ignore them. GPIO resets to zero; TX is idle
high, RX FIFO empty, interrupt disabled and sticky errors clear. The emulator-only
exit register at 0xffff0004 is not an FPGA peripheral.

## UART receive and interrupts

`mica_uart_rx.v` is plain Verilog-2005. Its two input synchronizer flops carry
`ASYNC_REG` attributes. An integer `CLOCK_HZ / BAUD` divider must be at least four
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
