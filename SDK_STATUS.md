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
| `adrpc` | PC-relative arithmetic at XLEN32/64, `ADRPC16` ELF relocation | Forward/backward cross-object addresses, range/alignment/template rejection |
| `wfi` / `stop` | Wakeable sleep / terminal halt | Masked external wake, handler return, timer wake, no requests during sleep |
| XLEN64 `ldw` | Sign extension in 2.0 | Legacy zero extension retained in compatibility mode |
| 8/16 register profiles | All three 2.0 RTL profiles build | MICA-2C: 8; MICA-2E/2L: 16; resource cost recorded |
| 1.0 compatibility | Retained | 14 frozen images and legacy retirement regressions |
| ELF ISA revision | Writer, reader, linker, emulator and inspector agree on MICA2 bit 16 | 32/64-bit ELF end-to-end tests; mixed object/runtime versions rejected |
| Formal checks | Component scope | Adder equivalence, SRAM properties, bounded FIFO; no whole-core proof |
| Synthesis | Yosys Xilinx 7-series mapping | All three 2.0 profiles and four compatibility configurations |
| Arty A7 | Board-top simulation, checked pins, restored Vivado script | Physical boot, placement/routing and timing closure pending |
| Schematics | All 31 drawing paths refreshed | DOT/SVG/PNG/PDF, Yosys port checks, SHA-256 source/preview manifest |
| RISC-V comparison | Assembler-measured code-size advantage on counted loops | Byte-copy body 6 vs 16 bytes RV32IC, 12 bytes with Zcb |
| Power / Fmax | Unmeasured | No lower-power or faster-clock claim |
| C / LLVM backend | Not implemented | Assembly toolchain is available |
| SIMD / multicore | Emulator / proposal | No production RTL subsystem or protected task isolation |

The current processor remains a single-issue multicycle reference. Tool-based
verification does not establish production readiness, independent laboratory
validation or physical electrical behavior. The 100 MHz board constraint is a
target, not a timing-closure result.
