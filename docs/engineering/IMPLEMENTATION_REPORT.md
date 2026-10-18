# MICA 1.0 engineering r2 implementation report

## Scope delivered

The repository now has a transactional scalar multicycle reference CPU and a
matching 32/64-bit reference emulator, an executable normative ISA, real separate
assembly compilation/linking, synchronous FPGA memory, timer/context firmware,
retirement verification, measured experiments and release/CI flows. The release
remains MICA 1.0. This is a substantial implementation milestone; it does not
finish every long-term acceptance criterion in the project brief.

Implemented source includes `rtl/mica_core_txn.sv`, the legacy adapter in
`rtl/mica_core.sv`, `rtl/mica_soc.sv`, portable `rtl/verilog/mica_sram_txn.v`,
`sim/emulator.cpp`, `toolchain/common/elf.hpp`, assembler/disassembler/linker and
ELF utilities, shared ISA/profile descriptions and generated consumers. The
[source inventory](CHANGED_FILES.md) records all changed files. The specification lives under
`docs/architecture`; toolchain, hardware and verification guides have one
current authoritative location, with legacy entry-point redirects.

## Correctness repairs

The eight-bit short opcode no longer truncates into six bits. Illegal encodings,
odd jumps and bus errors cannot leak register or link writes. F commits pointer
updates only after successful completion. Signed offsets and XLEN32 address wrap
are explicit. Fetch/data ports hold accepted state through latency and backpressure.
Reset cancels ownership with the fabric. Synchronous RAM is actually connected;
its registered read structure maps to BRAM rather than relying on combinational
read timing. Unused multiplier/B/CSR expressions are explicitly gated at constant
profile boundaries, because illegal flags alone retained unwanted hardware.

CSR permissions and reserved IDs agree, cycle/retirement counters work, a real
timer/comparator delivers interrupts, and exceptions save a defined PC/value.
SC requires both reservation address and width; vector transfers validate the
whole range before effects. Assembler depth/file/expansion bounds prevent stack
and allocation abuse. ELF offsets, strings, symbols, section sizes, relocation
arithmetic/templates and input totals are checked. Disassembly preserves reserved
bytes and prints byte comments correctly. The benchmark parser reads retirement
counts instead of an obsolete cycles label.

## Working tools and firmware

`mica-as`, `mica-ld`, `mica-dis`, `mica-run`, `mica-objdump`, `mica-nm`,
`mica-objcopy` provide help/version and real functions. The ELF64 subset uses an
experimental unassigned machine ID and a single image section; no generic Unix
ELF claim is made. It links all nine advertised relocation types with local,
global and weak symbols. The three-file startup/application/runtime example
clears BSS, computes CRC32 and prints through MMIO UART. Round trips preserve
all halfwords and random long envelopes. CLI debugging supports step, break,
watch, register/CSR/memory inspection and explicit state modification.

UART/GPIO/RAM/arithmetic/timer self-test and two-task preemption execute in both
reference emulation and SoC simulation. The HDL UART test samples the actual 8N1
pin and checks the message. The scalar signed16-bit FIR is checked against an
independent Python convolution. A software bounded-copy helper rejects range
and addition overflow before writing buffers. The VHDL watchdog runs under
GHDL and, through converted Verilog, delivers a real SoC interrupt. The new VHDL CRC-32 engine has a transactional SystemVerilog adapter; Verilog-2005 UART RX and a 16-byte FIFO provide buffered serial input and level interrupts. CRC, three receive interrupts and physical-pin echo pass on both XLENs, using the GHDL conversion flow.

## Evidence and measurements

Final commands/results are archived under [results](results/README.md) and summarized below. All 14 original binary fixtures retain their SHA256 and
match the shipped r1 emulator's registers/output; the ledger is
`isa/compatibility.json`. The infinite blink fixture is compared under a bounded
execution budget. Earlier baseline logs are retained next to AUDIT.md.

Fetch experiment: identical checked programs, five deterministic memory-delay
seeds, reuse disabled/enabled. CRC32 median cycles fell from 6837 to 5276 and
fetch transactions/retirement from 1.012 to 0.596. The copy example fell from 757
to 595 median cycles. These are multicycle RTL simulation results, without a
physical clock, energy measurement or external ISA baseline.

Standalone add/sub experiment: 10000 vectors, 90% narrow, formal equivalence for
all inputs. Generic 6-LUT mapping used 243 cells for conventional and 244 for
segmented arithmetic. Upper internal adder-result transitions were 160682 and 30104 respectively.
These are stable-value RTL transitions, not capacitance-weighted power or energy.
The segmented unit is not integrated into the main 64-bit core.

Mapped 4KiB SoCs with Yosys/7-series primitives: MICA-C uses 4499 LUTs, 983 FFs,
zero DSP48 and one RAMB36; MICA-E uses 6198 LUTs, 1508 FFs, six DSP48 and one
RAMB36; MICA-64 uses 14782 LUTs, 2885 FFs, 23 DSP48 and two RAMB36. UART TX/GPIO are included. With UART RX/FIFO and the converted VHDL CRC engine enabled, MICA-E maps to 6580 LUTs, 1823 FFs, six DSP48 and one RAMB36. C omits PERF/T/M/F/B; E/64 include PERF and their manifest
extensions. These totals expose substantial remaining area cost. No claim of
competitive minimum area is justified yet. Standalone 64KiB RAM maps to 16
RAMB36. No post-route Fmax, vendor power result or physical measurement exists.

Host counted-loop measurement on Intel Core i7-9700, Linux, GCC15.2.1 Release,
five million iterations and median of three: 32-bit reference 29.9 MIPS, fast 54.5,
specialized loop 1012.4; 64-bit reference 30.2, fast 56.2, specialized loop 974.6.
Short native-loop runs include process-launch overhead and visible variation.
These are host emulation throughputs for one loop, not general JIT throughput
or physical processor performance. The earlier EPYC measurement is historical.

## Incomplete criteria and next work

A second pipelined core, general JIT/LLVM backend, arbitrary independent ELF
sections/debug metadata, full lexer/column diagnostics, protected user mode/MPU,
multicore memory ordering/inter-core interrupts, atomics and SIMD RTL, general RTOS runtime, full C library, hardware loop/bank/event mechanisms
and physical power data remain incomplete. The memory model explicitly limits
current hardware to one uncached hart; MICA-MP is rejected by profile selection.

Current schematics validate actual RTL nets/ports and provide editable DOT,
SVG/PDF previews and vendor board connections. They are architectural wiring
references, not custom PCB schematics or tapeout data. Vivado Tcl, bitstream
creation and physical programming are pending because those tools/hardware
were unavailable. Yosys mapping and simulation do not establish timing closure.

Next milestones: reduce the measured reference area with shared execution units
and narrower counters; extend long-encoding/CSR/fault/interrupt coverage; build
the performance pipeline against this retirement oracle; run the supplied
Vivado flow and board bring-up; then compare independent embedded cores under
the same physical memory/clock/energy methodology. Do not add multicore or DSP
hardware claims until their ordering/numerical tests exist.

## Final validation

`python3 scripts/verify.py --all --build-dir build/baseline` passed all 20
logged stages: GCC Release build, seven CTest groups, 16 make targets including
the peripheral suite, Verilator lint, six configured RTL drivers, differential
retirement, profile faults, formal checks, four mapped SoCs, two diagram checks,
two measured hardware experiments and actionlint. The retirement suite compared
250 XLEN32 and 245 XLEN64 programs under three memory-delay seeds: 1485 runs,
plus six reset replays and four interrupts during outstanding memory requests.
Twelve additional profile programs check disabled operations and exact faults.

The Clang Debug ASan/UBSan configuration passed nine CTest groups, including
10,000 seeded ELF libFuzzer executions. LeakSanitizer ran with host process
inspection available; its sandbox failure was not suppressed. Engineering tests
include 14 cases and disassembly covers all 65536 halfwords plus randomized
long encodings. All 27 published source examples assemble; 24 execute under the
reference emulator, with the UART example supplied explicit input bytes. The
macros fragment, endless LED blinker and external-watchdog wait image have
different execution requirements. The watchdog has its own SoC test; the
three-object startup/application/library program also links and executes.

Native VHDL CRC tests check the standard vector, an independent MSB-polynomial
256-byte reference, busy input rejection, clear and reset. Verilog-2005 tests
check all UART byte values, adjacent frames, false starts, framing/break and
reset; FIFO simulation checks 8000 deterministic operations. Both XLEN SoCs
check CRC, three receive interrupts, state restoration and actual serial echo.
The actual Arty A7 top also passes with 100 MHz input, 4 KiB SRAM, RX/CRC enabled, synchronized reset release, timer IRQ, LEDs and serialized self-test text. This is simulation, not a measured board boot. The CRC adapter test checks held responses, busy stalls, invalid accesses and
reset ownership. Verilator lint includes RX and the converted CRC engine.

Formal results are deliberately narrow: all-input combinational ALU equivalence,
small SRAM response ownership/stability/reset proof, and a 16-cycle FIFO
ordering/occupancy bounded check against an independent queue. A FIFO induction
attempt did not close with head-only observable assertions; no inductive FIFO
claim is made. New-error/clear overlap and all peripheral reset races remain
coverage work. The final regression has zero failing test groups. One original
integration comparison is skipped because the external v0.1 SDK is unavailable.

Vivado execution, post-route timing, actual board programming/boot, physical
power, GitHub-hosted matrix execution and macOS execution were not performed
locally. These are pending validation, not passing results. No ISA comparison
or energy-superiority claim is justified by this revision.

Release artifacts are generated under `build/releases`: a CPack Linux binary
SDK and a deterministic source archive with `SHA256SUMS`. Packaging and clean
archive smoke-test results are recorded in [release validation](results/release.json).
The source archive keeps historical Linux convenience binaries as fixtures;
current tools are built from source or supplied in the CPack SDK.
