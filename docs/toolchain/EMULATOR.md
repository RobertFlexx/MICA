# Emulator

`mica-run` executes a flat image at 0 or the constrained ET_EXEC format at its
section address and entry. It rejects ET_REL and ELF feature/XLEN mismatches.
RAM defaults to 1MiB and is bounded to 4096..512MiB. Program input is bounded;
all RAM accesses and natural alignment are checked before effects.

Default execution is the reference interpreter. --fast handles selected short
scalar instructions and dbnz, falling back to reference execution for everything
else. --native-loops specializes one addi/backward-dbnz shape; it is not a general
JIT or executable-code emitter. It uses no writable/executable memory mappings.
Tracing or T falls back to the reference path for observability/correctness.
`tests/fast_paths.py` compares engine results, including step budgets and fallback.

Use --steps N for an attempted-instruction budget, --peek ADDR:COUNT for bounded
RAM inspection, --trace for human fetch tracing, --retire-trace FILE for JSONL,
--irq-at N for a single source 0 software-pending injection after N retirements,
and --debug for the CLI. --quiet suppresses register dumps. Exit0 means ordinary
halt,1 means nonzero emulator host-exit value, and 2 means load/execution error.
The legacy host-exit MMIO register is emulator-only.

The functional model advances counters once per attempted instruction. It has
no physical pipeline, memory latency model, multi-hart scheduler or cycle-stepped
RTL timing. Report emulator throughput as host-dependent emulated instructions
per second, never MICA silicon MHz. Device TX completes immediately; real SoC
TX serializes and can backpressure writes.

`--uart-input HEX` preloads up to 16 explicit bytes into the RX device. For
example `--uart-input 414243` provides ASCII ABC. RX level interrupts, FIFO pop,
capability discovery and CRC-32 MMIO follow the [peripheral contract](../hardware/PERIPHERALS.md).
The functional CRC finishes immediately; device timing is measured in RTL.
