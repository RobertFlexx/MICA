# MICA 2.0 hardware and schematics

## Build selection

The transactional execution logic lives in `rtl/mica_core_txn.sv`.
`MICA2=1` enables 2.0 through `mica_core`, `mica_soc` and the Arty wrapper.
`MICA2=0` preserves the 1.0 decode, WFI halt semantics and frozen firmware.
MICA-2C uses eight register slots; MICA-2E/2L use sixteen.

## Execution paths

Stack addressing is `old SP + (slot << log2(XLEN/8))`, wrapping at XLEN.
The existing LSU owns request, response, error and pending writeback. A load
does not update its destination before successful completion, and an error
discards pending writes. Stores returning error must have no memory side effect.

`dbnz.s` reuses scalar decrement/branch logic and has a signed six-bit
halfword displacement from PC+2. `adrpc` uses the instruction PC and a signed
16-bit halfword displacement. Both use existing result and COMMIT paths.

WFI sets `q_wait`, retires and enters SLEEP. Raw pending events wake it;
interrupt delivery additionally requires T and the enable/mask conditions.
No instruction/data request or new retirement occurs while waiting.
The clock and enabled counters continue. STOP sets `q_stop` and remains
terminal until reset. Neither state implies a physical power gate.

The core remains single-issue and multicycle, with one outstanding transaction
per port. F can queue destination and base writes together. Those are two
logical writes in COMMIT; a one-port register bank is still a research option.

## Diagrams

The [complete index](DATAPATH.md) covers every refreshed drawing path.
The six `schematics/mica2` diagrams have editable DOT and SVG/PNG/PDF previews:

| Drawing | Subject |
| --- | --- |
| [Encoding](../../schematics/mica2/01-isa-encoding.svg) | Short stack/branch/STOP allocations and extended ADRPC |
| [Datapath](../../schematics/mica2/02-core-datapath.svg) | Fetch, decode, ALU, pending effects, LSU and COMMIT |
| [Stack/memory](../../schematics/mica2/03-stack-and-memory.svg) | Addressing, handshake and precise access faults |
| [WFI/traps](../../schematics/mica2/04-wfi-and-traps.svg) | q_wait, SLEEP, pending wake and terminal STOP |
| [FPGA topology](../../schematics/mica2/05-fpga-topology.svg) | SRAM, optional RX/CRC, real board boundary and IRQ tie-off |
| [Profiles](../../schematics/mica2/06-profiles-and-cost.svg) | XLEN/register configuration and implementation tradeoffs |

The `schematics/current` drawings are regenerated with Yosys and MICA2=1.
The overview generator refreshes all nineteen older top-level paths, derives
board pins from XDC and hashes every source/preview. These are architectural
drawings, not transistor or PCB fabrication schematics.

## Executed verification

```sh
make -C rtl sim-mica2-32 sim-mica2-64 sim-mica2-timer32 sim-mica2-timer64
python3 scripts/build_rtl_sim.py --profile MICA-2C
python3 scripts/build_rtl_sim.py --profile MICA-2E
python3 scripts/build_rtl_sim.py --profile MICA-2L
python3 verification/differential/mica2.py --tools build
python3 scripts/synthesize.py --tools build
```

Icarus tests both widths, including timer sleep/return and STOP stability.
Verilator compares 129 new runs and nine reset replays with the interpreter
under randomized memory stalls and latency. Yosys maps all three 2.0 profiles.
The [verification report](../engineering/MICA2_VERIFICATION.md) links raw
evidence and component formal scope.

## Performance

The [RISC-V comparison](../research/RISCV_COMPARISON.md) demonstrates smaller
counted memory loops from assembler output. The [synthesis guide](SYNTHESIS.md)
records mapped area costs. Hardware comparisons require matched cores,
SRAM, peripherals, tools and clock constraints.

Vivado place/route, timing closure, physical board boot and rail power remain
pending.
