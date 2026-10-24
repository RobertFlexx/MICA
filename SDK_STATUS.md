# MICA 2.0 implementation status

MICA 2.0 has local software, RTL simulation, retirement-comparison and mapped
synthesis evidence. The [verification report](docs/engineering/MICA2_VERIFICATION.md)
and [archived results](docs/engineering/results/mica2/README.md) record the commands
and limits. Original MICA 1.0 evidence remains separately dated.

| Area | Status | Evidence / limitation |
| --- | --- | --- |
| 2C compact opcodes | Implemented in tools and transactional RTL | XLEN32/64 Icarus tests; Verilator retirement comparison |
| `ldsp` / `stsp` | Full-width stack access and precise faults | All slots, SP alias, x0 access, alignment/access errors, address wrap |
| `dbnz.s` | Six-bit signed halfword displacement | Taken/exit, counter wrap, both displacement limits |
| Compact branch ELF | `PCREL6` for local and external `dbnz.s` targets | XLEN32/64 link/run, split-field/template/revision/range checks |
| ELF alignment | Object `.align` requirements survive linking | Absolute placement with nonzero origins; padding checked against region size |
| `adrpc` | PC-relative arithmetic at XLEN32/64, `ADRPC16` ELF relocation | Forward/backward cross-object addresses, range/alignment/template rejection |
| `wfi` / `stop` | Wakeable sleep / terminal halt | Masked external wake, handler return, timer wake, no requests during sleep |
| XLEN64 `ldw` | Sign extension in 2.0 | Legacy zero extension retained in compatibility mode |
| 8/16 register profiles | All three 2.0 RTL profiles build | MICA-2C: 8; MICA-2E/2L: 16; resource cost recorded |
| 1.0 compatibility | Retained | 14 frozen images and legacy retirement regressions |
| ELF ISA revision | Writer, reader, linker, emulator and inspector agree on MICA2 bit 16 | 32/64-bit ELF end-to-end tests; mixed object/runtime versions rejected |
| Trap diagnostics | Illegal-instruction TVAL contains raw instruction bytes | XLEN32/64 results agree with and without retirement tracing |
| SDK release workflows | Dependency-free source discovery, installed 1.0/2.0 checks and extracted-source CI | Local validation in the [revision report](docs/engineering/WORKFLOW_ISA_REVISION.md); new remote run pending |
| Formal checks | Component scope | Adder equivalence, SRAM properties, bounded FIFO; no whole-core proof |
| Synthesis | Yosys Xilinx 7-series mapping | All three 2.0 profiles and four compatibility configurations |
| Arty A7 | Board-top simulation, checked pins, restored Vivado script | Physical boot, placement/routing and timing closure pending |
| Schematics | All 31 drawing paths refreshed | DOT/SVG/PNG/PDF, Yosys port checks, SHA-256 source/preview manifest |
| RISC-V comparison | Assembler-measured code-size advantage on counted loops | Byte-copy body 6 vs 16 bytes RV32IC, 12 bytes with Zcb |
| Power / Fmax | Unmeasured | Requires physical power and timing measurements |
| C compilation | Experimental subset | Clang IR lowering for MICA-2C/2E; calls, recursion, arrays, structures, volatile MMIO and native/RTL checks; full LLVM backend incomplete |
| Signed F | Implemented in tools and scalar RTL | `ldpi.sb/sh/sw`, sign/stride boundaries and precise faults; requires development r2+ |
| Register parity | Optional experimental detector | Fail-stop before decode effects; targeted register sweep; no correction or SRAM protection |
| Sensor demonstration | Compiled C and SoC simulation | Timer wake, CRC-8 packets, watchdog and sleep activity; physical energy unmeasured |
| MICA-2D / 2R / 2S | Proposed | DSP, reliability and security requirements incomplete; tool selections rejected |
| SIMD / multicore | Emulator / proposal | No production RTL subsystem or protected task isolation |

The processor is a single-issue multicycle reference. Physical board validation,
routed timing and electrical measurements are pending. The board constraint
targets 100 MHz.

The [embedded refinement report](docs/engineering/EMBEDDED_REFINEMENT.md) records
current code-generation losses, observed wake behavior and remaining acceptance
gates. Historical evidence above is retained with its original scope.
