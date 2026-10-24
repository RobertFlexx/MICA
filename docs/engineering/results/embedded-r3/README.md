# Development r3 evidence

`scripts/archive_embedded_evidence.py` copies executed results into this directory.
`environment.json` records tool versions, source hashes and the saved synthesis
baseline commit. Logs are gzip-compressed with deterministic headers.

| Artifact | Scope |
| --- | --- |
| `regression.json`, `ctest.xml`, `logs/` | Full local regression commands, status and output |
| `instructions.json` | Per-instruction assembly/disassembly/interpreter/RTL integration vectors |
| `compiler.json`, `compiled-density.json` | Native/RTL C checks and complete-ROM comparisons |
| `sensor.json` | Compiled sensor cycles, UART, wake and selected-signal activity |
| `faults.json` | Every targeted injection, including undetected corruption |
| `synthesis.json`, `baseline-synthesis.json` | Matched 4 KiB SoC mapping; no routed timing |
| `core-revision.json` | Baseline/current firmware and signed DSP measurements |
| `differential*.json`, `profiles.json` | Architectural retirement and configuration tests |
| `formal/` | Component proof output, not whole-core verification |
| `sanitizers.log.gz`, `sanitizer-details.log.gz` | ASan/UBSan/LeakSanitizer and seeded fuzz output |

The [engineering report](../../EMBEDDED_REFINEMENT.md) explains results and limits.
Physical energy, routed maximum frequency, board operation, pipeline, security
isolation and vector/atomic hardware remain unverified or unimplemented.
