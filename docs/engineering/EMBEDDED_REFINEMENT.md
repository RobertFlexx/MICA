# Embedded refinement, MICA 2.0 development r3

This revision improves the existing multicycle implementation and experimental
C translation path. It does not complete the project roadmap. Verification
results below distinguish executed checks from incomplete acceptance gates.

## Audit and implementation status

The audit covers the encoding JSON, software tools, profiles, runtime, RTL,
FPGA projects, diagrams, workflows and existing evidence. Instruction-level
results are generated separately by `verification/instructions/run.py`.

| Subsystem | Classification | Actual implementation and remaining work |
| --- | --- | --- |
| Scalar base, X/M/F/B/T and 2C | Experimental | Assembly, disassembly, interpreter and multicycle RTL; instruction vectors and fault/latency regressions, not exhaustive verification |
| A | Software only | Single-interpreter reservation/atomic operations; no shared-memory atomic RTL |
| V | Software only | Eight 128-bit vector registers in the emulator; no integrated vector datapath |
| MICA-2D/2R/2S | Proposed | Dependency descriptions only; tools reject these profile selections |
| Pipelined CPU | Proposed | No implemented pipeline to stabilize or qualify |
| C compilation | Partially implemented | Restricted Clang IR lowering, local high-register allocation, frames/calls/structures/arrays/volatile MMIO; unsupported constructs fail explicitly |
| ELF/linker | Partially implemented | Multi-object symbols, checked relocations, aligned SRAM images; independent sections/NOBITS/ROM startup and garbage collection incomplete |
| Runtime | Partially implemented | Tested assembly routines and compiled sensor platform; no complete freestanding C library |
| Verilog devices | Experimental | SRAM, UART, FIFO and standalone SPI, independently simulated and synthesized |
| VHDL components | Experimental | CRC, event counter and windowed watchdog; native tests and converted-netlist integration |
| Register integrity | Experimental | Optional parity and fail-stop behavior, targeted bit injection; no state correction or memory ECC |
| Privilege/isolation/secure boot | Proposed | No MPU, protected key store, immutable root or authenticated debug |
| FPGA | Experimental | Arty top simulation and Yosys mapping; physical boot, Vivado routing and timing unverified |
| Power | Experimental | RTL selected-signal transition measurement; physical power and energy unmeasured |

## Corrections and improvements

Constant pointer/GEP lowering now accepts the expressions Clang emits for arrays
and volatile MMIO. The previously removed narrow-value test is restored. Short
stack accesses reduce compiler spill code. MICA-2E can retain local SSA values
in x8..x11, with explicit call and basic-block boundaries. Cross-object calls,
recursion and callee-save checks execute against native results and RTL.

Enabled interrupts enter directly from SLEEP rather than traversing START.
Masked pending events still wake without forced handler delivery. Register parity
is optional and absent from the minimum configuration by default. The fault
campaign records both detected failures and silent unprotected corruption.

CI again fails on stale source checksums and schematic checks. Source archives
are validated instead of silently regenerating their manifest inside CI.
Formal timeouts retain logs. SPI ownership/completion checks supplement the
independent four-mode serial slave.

The preceding development r2 work added signed F loads, reproducible encoding
overlap validation, instruction-level conformance execution, aligned-long fetch
completion, selective instruction-buffer invalidation, portable UART TX/SPI,
VHDL event counting and the integrated windowed watchdog. These remain compatible
2.0 development additions; signed F uses previously reserved subopcodes.

## Reproduce

```sh
python3 scripts/verify.py --all --build-dir build/verify-r3
python3 verification/instructions/run.py --tools build/verify-r3 --rtl build/rtl --report docs/verification/INSTRUCTION_MATRIX.md
python3 benchmarks/compiled_density.py --tools build/verify-r3
python3 scripts/test_sensor_demo.py --tools build/verify-r3
python3 scripts/test_fault_injection.py --tools build/verify-r3
```

The compiled density comparison uses identical C input and frontend `-O0`, flat
ROM placement and explicit startup on MICA, RISC-V and Thumb. It includes code,
constants, initialized data and alignment. MICA's prototype code generation
currently loses substantially. Register allocation, backend optimization and
target execution coverage differ, so these results are not ISA density rankings.
No matched competitor area, cycle or energy advantage is established.

The saved-core comparison additionally needs repository history at `22b5571`.
With the pinned HDL tools on PATH, its retirement drivers can be rebuilt separately:

```sh
mkdir -p build/baseline-src
git archive 22b5571 | tar -x -C build/baseline-src
python3 build/baseline-src/scripts/build_rtl_sim.py --profile MICA-2E --build-dir build/baseline-rtl
python3 build/baseline-src/scripts/build_rtl_sim.py --profile MICA-2L --build-dir build/baseline-rtl
python3 benchmarks/core_revision.py --tools build/verify-r3 --baseline build/baseline-rtl
```

Source archives contain current code and historical result records; they do not
contain the old Git tree. Current synthesis, sensor, C and fault measurements can
be reproduced directly from the archive.

## Executed results

| Check | Result |
| --- | --- |
| GCC Release | 16 CTest groups passed, including compiled firmware and frozen 1.0 images |
| Clang Debug, ASan/UBSan/LeakSanitizer | 18 groups passed, including 10,000 seeded ELF fuzz runs |
| Instruction integration | 153 entries; scalar RTL compared at applicable XLENs under three stall seeds; A/V explicitly software-only |
| RTL differential | 1,485 compatibility runs; 213 MICA 2.0 runs and 213 parity-enabled runs, plus reset replays |
| Configured profiles | 12 programs, including disabled-extension faults |
| C differential | 28 C/profile combinations, native result oracle, three emulator modes and three RTL stall seeds |
| Fault campaign | 134 injections: 32 register bits and 32 SRAM bits per parity setting, plus selected FSM/PC/fetch errors |
| Component formal | Adder, SRAM, FIFO and SPI checks passed; no whole-core proof |
| HDL integration | Icarus, native GHDL, converted VHDL SoC, Verilator lint and nine mapped synthesis configurations passed |
| Physical FPGA, timing, energy | Not executed or measured |
| Installed SDK and source release | Installed C/assembly tools and sensor firmware pass; source archive checksum validation, fresh build and 16 CTest groups pass |

LeakSanitizer initially failed under restricted process inspection; it passed
with inspection access and leak detection enabled. Formal checks use a configurable
timeout and retain timeout logs. Final source checks do not suppress failures.
Optimized emulator checks run without retirement logging, which deliberately
selects the reference path. Unsupported accelerated cases retain their documented
interpreter fallback.

The sensor image is 1,220 bytes. Its SoC simulation takes 53,715 clocks, with
7,868 asleep and 45,847 active. Four timer interrupts enter one clock after the
pending condition is observed in SLEEP. This excludes external synchronizers and
does not bound an interrupt arriving during a stalled memory transaction.
Stable sleep intervals show zero transitions in the selected registered datapath
signals, while clock/timer counters remain active. This short relative schedule
is not an ultra-low-duty battery-life demonstration.

For the multi-file C test, MICA-2E reduces measured loads/stores from 335 to 149
relative to MICA-2C. The ABI-check firmware measures median 9,460 versus 8,615
cycles across three bus-stall seeds. The expanded test includes four extra
callee-save sentinel initializations; these counts are test results, not an
isolated register-file area/performance comparison.

Complete ROM comparison for the same array/structure/call/recursion C program:

| Target | ROM bytes |
| --- | ---: |
| MICA-2C | 896 |
| MICA-2E | 920 |
| RV32I | 404 |
| RV32IC / RV32EC / RV32IC+Zcb | 244 |
| Cortex-M0+ | 208 |
| Cortex-M4 | 204 |

All use frontend `-O0`; backend allocation/optimization differ. Competitor images
were built, not target-executed. This is an early compiler baseline and a clear
loss for MICA, not a claim about the best achievable ISA density. Before compact
stack selection and local allocation, both MICA images measured 1,120 bytes.

Matched Yosys Xilinx 7-series SoCs, with 4 KiB SRAM and identical profile settings:

| Configuration | LUTs | Flip-flops | DSP48 | RAMB36 |
| --- | ---: | ---: | ---: | ---: |
| MICA-2C baseline `22b5571` | 4,758 | 982 | 0 | 1 |
| MICA-2C r3 | 4,736 | 983 | 0 | 1 |
| MICA-2E baseline | 7,333 | 1,766 | 6 | 1 |
| MICA-2E r3 | 7,304 | 1,767 | 6 | 1 |
| MICA-2E r3 + register parity | 7,602 | 1,783 | 6 | 1 |
| MICA-2E r3 + RX/CRC/watchdog | 7,954 | 2,183 | 6 | 1 |
| MICA-2L baseline | 14,932 | 2,887 | 23 | 2 |
| MICA-2L r3 | 15,128 | 2,888 | 23 | 2 |

Parity costs 298 LUTs and 16 flip-flops in this matched expanded configuration.
The 64-bit implementation grows; no general area advantage is established.
Mapping is not routed timing or physical power evidence.

Five-seed firmware comparisons against the saved baseline core show arithmetic32
100 to 90 median cycles, arithmetic64 259 to 217, copy 595 to 554, strings 907 to
845, and division 2,887 to 2,892. The small division regression is retained.
The signed dot-product kernel measures 6,069 to 4,373 cycles and 18 to 14 loop
bytes. Complete images, including setup and both input arrays, are 320 and
318 bytes. These are handwritten workload results with an independent numerical
oracle, not matched competitor DSP measurements.

Raw results, source hashes and logs are in
[embedded-r3 evidence](results/embedded-r3/README.md). The
[known-issues register](KNOWN_ISSUES.md) identifies the remaining implementation
and verification work.

## Open acceptance gates

ISA/RTL completeness, a maintained optimizing compiler backend, pipelined RTL,
hardware SIMD/atomics, independent ELF sections, hard memory-response bounds,
memory protection, secure boot, physical power/timing and board qualification
remain incomplete. The sensor demonstration is functional compiled firmware;
the industrial/remote probes and signed DSP kernel do not complete production
demonstrators for all five markets. No subsystem is declared production-ready.
