# Archived r2 measurements

These files were produced on 2026-10-17 on the host recorded in
[environment.json](environment.json). [regression.json](regression.json) records all
20 executed stage commands, exit status and elapsed time. The `regression` directory
contains gzip-compressed raw logs. `software.log.gz` and `sanitizers.log.gz` contain
the individual CTest outputs, including the explicit legacy external-SDK skip and
the seeded 10000-run fuzz campaign.

[Fetch measurements](fetch-results.json) retain all five memory-delay seeds per
configuration. [Emulator measurements](emulator-results.json) retain all timing
repetitions and host identity. [Differential results](differential-results.json)
record all 1485 ordinary runs; reset/IRQ replays are reported in the raw log. The
synthesis directory contains complete per-configuration primitive counts and
compressed tool logs. `sram-64KiB.log.gz` records the independent BRAM test. ALU
activity/mapping data and logs live under `alu-research`. Formal logs retain the
proof/bounded status and explicit assumptions from the source harnesses.

`peripherals.log.gz` records native Verilog-2005 and VHDL simulations, GHDL
conversion, enabled-SoC lint and CRC/RX firmware on both XLENs. The `waveforms`
directory contains compressed VCDs for native VHDL CRC/watchdog, Verilog UART
RX/FIFO, SystemVerilog CRC bus transactions both SoCs and the actual Arty top.
Decompress with `gzip -dk file.vcd.gz` before opening in a waveform viewer. These
are simulation waveforms, not measured voltage traces. Regenerate the reports with
BUILDING.md and archive them with `scripts/archive_evidence.py`.

[Release validation](release.json) records install/archive smoke tests. Build
artifacts themselves remain under `build/releases` and are reproducible from the
documented commands. No physical FPGA, placed/routed timing, power or
independent-ISA comparison result is included.

[CI results](ci.json) identify implementation commit `4e57212` and its seven
successful jobs, including macOS. The raw local logs above retain the host and
commands from their original execution.

For current MICA 2.0 evidence, use the separately archived
[2.0 results](mica2/README.md). The r2 files above retain their original 1.0 scope.
