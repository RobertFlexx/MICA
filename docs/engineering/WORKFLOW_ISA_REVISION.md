# Workflow and ISA integration revision, 2026-10-18

Commit `fbefc07` passed local software tests but failed its
[GitHub software and sanitizer jobs](https://github.com/RobertFlexx/MICA/actions/runs/39117058868).
The failed Linux job log shows `format_safety` calling `format_code.py`, which
failed with `FileNotFoundError: rg`. Ripgrep was absent from the runners.
Hardware and workflow lint jobs passed for that commit.

## Corrections

| Finding | Reproduction or effect | Correction |
| --- | --- | --- |
| Undeclared formatter dependency | `format_safety` failed on CI without ripgrep | Shared source discovery uses Git when available and Python directory traversal otherwise; isolated tests remove both tools from PATH |
| Literal truncation | `li32 x1,0x100000001` assembled as 1 in 2.0 mode | Check the full literal's range before any shorter encoding is selected |
| Missing compact branch relocation | `-c` rejected `dbnz.s x2,loop` even for a local label | `PCREL6` ID 11 patches the existing split immediate; range, alignment, revision and template checks retain the two-byte encoding |
| Lost object alignment | `.align 256` could become a 16-byte-aligned fragment after linking | Record the maximum object alignment in ELF and align absolute placement with bounded padding |
| Trace-dependent TVAL | An illegal instruction saved zero without `--retire-trace` | Capture faulting instruction bytes whenever traps are enabled |
| Wrong disassembly revision | A legacy ELF could display reserved bytes as 2.0 instructions | Decode ELF using its revision/features; expose `--mica1`/`--mica2` for raw images and emit the ELF's correct `.arch` |
| Stale verification evidence | A missing HDL tool could leave a prior successful summary | Invalidate the stage summary before preflight and emit CTest JUnit output |
| Release coverage gap | Installed smoke tests covered legacy ELF only | Exercise installed 2.0 branches, PC-relative addresses, alignment and disassembly at both widths; add extracted-source CI |
| Archive contamination | Alternate build directories could enter source archives | Share directory exclusions with the formatter; test deterministic archives without Git and with build directories present |

`PCREL6` uses the existing compact branch encoding. Relocation IDs 1..10 retain
their meanings; ID 11 requires 2.0 metadata. Regression tests preserve raw
instruction compatibility and the frozen 1.0 firmware. The stack specification
clarifies that `ldsp sp` calculates its address from the old SP before replacing it.

## Validation

The reproducible commands are:

```sh
python3 scripts/verify.py --build-dir build
ctest --test-dir build-san --output-on-failure --parallel 4
actionlint .github/workflows/ci.yml
cmake --install build --prefix "$PWD/build/install"
cpack --config build/CPackConfig.cmake -B build/releases -G TGZ
python3 scripts/package_source.py
python3 scripts/check_release.py --binary build/releases/mica-sdk-2.0-Linux-x86_64.tar.gz --source build/releases/mica-sdk-2.0-source.tar.gz
```

The Clang build uses ASan, UBSan and `MICA_FUZZ=ON` as described in
[BUILDING.md](../../BUILDING.md). LeakSanitizer tests ran with process-inspection
access and leak detection enabled. `tests/isa_contract.py` covers both widths, local and
external compact targets, exact range limits, malformed templates and metadata,
output preservation, absolute alignment and traced/untraced traps.

| Check | Local result |
| --- | --- |
| GCC 15.2.1 Release | 12/12 CTest groups pass; all 14 frozen firmware fixtures retained |
| Clang 23.1.3 Debug, ASan/UBSan/LeakSanitizer | 14/14 CTest groups pass, including 10,000 seeded libFuzzer runs |
| Installed binary SDK | Both revisions and XLEN32/64 link, execute, disassemble and convert successfully; startup/UART/CRC checks pass |
| Extracted source SDK | Source checksums, fresh Release configure/build and 12/12 CTest groups pass without a Git checkout |
| Formatter and archive safety | Four regression cases pass, including no partial writes, no-Git/no-ripgrep discovery, deterministic archives and stale-evidence invalidation |
| Workflow | actionlint 1.7.12 passes; local runner records four passing stages and JUnit output |
| Generated ISA/docs/drawings | ISA tables current; 70 Markdown files and four assembly snippets pass; MICA2 diagrams and schematic source/preview hashes check successfully |
| Formatting and patch hygiene | All 17 changed source/build files pass the selective format check; `git diff --check` passes |
| Full HDL regression | Not run: iverilog/vvp, Verilator, GHDL, Yosys and SBY unavailable |

Raw local logs and JUnit output are under `build/validation` and `build-san`.
Installed and clean-source release command output is in
`build/releases/source-validation.json`.

## Remaining work

Independent ELF sections, a C ABI/backend, area experiments, pipelined RTL and
physical board/timing/power validation are tracked in the [roadmap](../ROADMAP.md).
The RTL datapath is unchanged. Remote CI for this revision is pending.
