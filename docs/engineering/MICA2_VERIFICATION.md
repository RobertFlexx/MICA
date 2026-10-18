# MICA 2.0 verification report

The earlier statement that RTL had not been simulated or synthesized in this
environment is superseded by executed local HDL tests and Yosys mapping.
**Power and clock-speed advantages remain unmeasured.** These are local tool
results, not an independent hardware laboratory certification.

## Executed checks

| Check | Scope |
| --- | --- |
| Clang ASan/UBSan and libFuzzer | 11 CTest targets, including seeded 10,000-run ELF fuzzing; LeakSanitizer disabled because process inspection is blocked |
| Release build and CTest | Toolchain, emulator, 14 frozen firmware images, ISA generation, 2.0 regressions, all examples and executable documentation |
| Icarus SoC simulation | 2.0 compact loops at XLEN32/64; timer WFI wake and terminal STOP at both widths |
| Legacy HDL regression | Arithmetic, F, B, T, SRAM, watchdog, scheduler, UART/FIFO, CRC, both SoCs and actual Arty wrapper |
| Verilator retirement comparison | Legacy scalar tests plus 129 MICA 2.0 runs across 2C/2E/2L with three memory-delay seeds; nine new reset replays |
| Runtime assertions | Stable requests under stalls, x0, retirement rules, distinct F writes, no bus requests or extra retirement during delayed WFI wake |
| SBY / Z3 | Standalone adder equivalence, SRAM response properties, bounded FIFO ordering |
| Yosys | Seven complete 4 KiB SoC configurations mapped to Xilinx 7-series primitives |
| Drawings | Elaborated core/SoC ports, 31 drawing paths, source and preview hashes |
| RISC-V encoding comparison | LLVM-assembled RV32I, RV32IC and RV32IC + Zcb against MICA 2.0 |

The complete stage list, exit codes and elapsed times are in
[regression.json](results/mica2/regression.json). The
[environment record](results/mica2/environment.json) identifies tool versions
and source hashes. Compressed stage logs remain beside the reports.

## Defects repaired during verification

- Masked IRQs previously failed to wake the T-enabled emulator because wake
  eligibility incorrectly used the interrupt-delivery mask. Wake now uses raw
  pending events; handler delivery still uses interrupt enables.
- The fast/native fallback path retained the legacy WFI halt on 2.0 cores
  without T. MICA2 WFI now uses the reference sleep path in all engines,
  with regression checks for sleeping and waking.
- Compact stack effective addresses in the XLEN32 emulator did not wrap at
  32 bits. They now wrap consistently with the ISA and RTL.
- Two 64-bit decode expressions produced Verilator width warnings. Explicit
  XLEN arithmetic and a constant slot shift remove the ambiguity.
- The 2.0 source archive omitted the Vivado board build script. It is restored
  from 1.0 and also accepts a `mica2_short32` image with `MICA2=1`.

The new retirement cases cover all stack slots, x0 reads, SP aliases, address
wrap, compact branch displacement limits, counter wrap, signed PC-relative
limits, high registers, F copy loops, illegal fields, access/alignment faults,
ecall EPC, masked wake and interrupt handler return. Timer checks use expected
SoC outcomes separately because RTL clock ticks differ from emulator steps.

## Demonstrated advantage

The [RISC-V comparison](../research/RISCV_COMPARISON.md) records a six-byte
MICA F+2C byte-copy body versus sixteen bytes for RV32IC and twelve for RV32IC
with Zcb. The copy body uses three instructions versus six. The stack
save/restore case ties compressed RISC-V. These are specific encoding and
instruction-count advantages.

## Still pending

Vivado placement/routing, timing closure, physical FPGA boot, measured rail power,
maximum stable clock, thermal behavior and a matched RISC-V hardware experiment
remain pending. Yosys cell counts are mapped resources; simulation cycles are
memory-model dependent. Neither gives watts, joules or Fmax.

The formal checks do not prove the processor, interrupt timing, all legal
encodings or every peripheral interaction. No complete coverage closure is
claimed. The historical [1.0 r2 report](IMPLEMENTATION_REPORT.md) and its evidence
retain their original scope.

## Reproduce

```sh
python3 scripts/verify.py --all
python3 scripts/archive_mica2_evidence.py --build build/verify
```

See [BUILDING.md](../../BUILDING.md) for the HDL suite, LLVM tools and formatting.
