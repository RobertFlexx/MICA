# Contributing to MICA

Useful changes come with a small example that demonstrates the problem or the
new behavior. For instruction changes, start with the [ISA manual](docs/architecture/ISA.md)
and [audit](docs/engineering/AUDIT.md); the emulator and RTL need to agree on
both successful execution and faults.

## Architecture and compatibility

MICA keeps its 1.0 instruction encodings. Compatible implementation changes use
engineering revisions. Existing allocations and the frozen firmware fixtures
are part of that contract. A failing fixture needs an explanation and a fix,
rather than a freshly assembled replacement that happens to pass.

Allocations live in `isa/encodings/mica1.json`; configurations live in
`isa/profiles/profiles.json`. After editing them, run
`python3 scripts/generate_isa.py` and include the generated files in the commit.
Reserved-bit rules are enforced by `isa/encoding.hpp` and the RTL decoder.
Conformance tests should exercise the operation, its edge cases and relevant
illegal encodings.

## Testing a change

[BUILDING.md](BUILDING.md) lists the supported checks. Choose those affected by
the change and include the commands and results in the pull request.

Memory changes need tests for latency, response ownership, faults and reset.
Trap changes need a retirement comparison and a context-preservation case.
Peripheral changes need a test that observes the bus or serial pins. A store
that happens twice under backpressure is particularly unpopular with UARTs.

When a differential test fails, keep the first mismatching event and the input
that produced it. A field belongs outside the comparison only when its
platform-dependent meaning is documented, such as hardware clocks versus
interpreter steps.

## Reports and generated files

Keep RTL port names and generated drawings in sync. Benchmark reports should
include inputs, validated outputs, tool versions, configuration and raw results.
Area, timing and power are separate measurements; each needs its own evidence.

Generated build products and growing fuzz corpora stay outside commits. Checked-in
ISA tables, drawing sources and release evidence are intentional exceptions.
Use repository-relative paths in guides and scripts so another checkout can run
them without borrowing the original developer's directory layout.

Format SDK sources with `python3 scripts/format_code.py`; use `--check` for
a read-only check. Regenerate all schematic sets after RTL or generator changes.
