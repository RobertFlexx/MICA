# Emulator

`mica-run` loads a flat image at address 0 or a MICA ET_EXEC image at its section
address and entry. ELF objects must be linked first; XLEN and required features are
checked during loading. RAM defaults to 1 MiB and can be selected from 4096 bytes to
512 MiB. Memory ranges and natural alignment are checked before instruction effects.

## Execution engines

The reference interpreter is the default and defines the comparison behavior.
`--fast` handles selected short scalar instructions and `dbnz`, falling back to the
reference for other operations. `--native-loops` specializes one
`addi`/backward-`dbnz` pattern using compiled host code. It does not generate
executable memory or provide general basic-block translation.

Tracing or T uses the reference path to preserve observable boundaries.
`tests/fast_paths.py` compares engine results, step budgets and fallback cases. The
functional model advances counters per attempted instruction; RTL clocks also
include fetch, memory and control stalls.

## Running and inspecting a program

| Option | Behavior |
| --- | --- |
| `--steps N` | Limit attempted instructions |
| `--peek ADDR:COUNT` | Inspect a bounded RAM range after execution |
| `--trace` | Print instruction-fetch tracing |
| `--retire-trace FILE` | Write architectural JSONL events |
| `--irq-at N` | Inject source 0 software-pending after N retirements |
| `--debug` | Start the CLI debugger |
| `--quiet` | Suppress the register dump |
| `--uart-input HEX` | Preload up to 16 receive bytes |

Exit status 0 means normal halt, 1 means a nonzero emulator host-exit value, and 2
means a load or execution error. The host-exit register is specific to the emulator.
[Debugger commands](DEBUGGING.md) support interactive and scripted sessions.

## Devices and timing

`--uart-input 414243` supplies ASCII `ABC`. FIFO pops, receive-level interrupts,
capability discovery and CRC-32 follow the [peripheral register
map](../hardware/PERIPHERALS.md). Input is explicit; the emulator does not open host
serial ports.

UART transmit and CRC finish immediately in the functional model. The RTL UART
serializes bytes and can stall writes; its CRC engine takes eight clocks per byte.
Status-poll instruction counts can therefore differ while final results agree.
Cycle-stepped platform timing and multi-hart simulation remain open work. Host
throughput is reported in emulated instructions per second, with host and workload
details in the [benchmark results](../research/BENCHMARKS.md).
