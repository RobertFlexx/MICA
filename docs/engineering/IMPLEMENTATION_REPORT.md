# MICA 1.0 engineering r2 report

Engineering r2 replaces the immediate-memory CPU prototype with a transactional
32/64-bit multicycle reference core. It also adds ELF assembly and linking, precise
faults, timer firmware, peripheral blocks and retirement comparison. The ISA version
remains 1.0, with the existing encodings and all 14 firmware compatibility fixtures
preserved.

The [file inventory](CHANGED_FILES.md) lists changes from the original audit
baseline. [Archived results](results/README.md) contain commands, tool versions, raw
logs, benchmark runs and waveforms.

## Core and correctness repairs

The old short-opcode decoder truncated eight bits into six, allowing reserved
opcodes to alias valid operations. The new decoder retains the full field and
rejects reserved values. Decode stages pending effects; commit applies them only
after successful completion. Illegal encodings, odd jump targets and bus errors
therefore leave destination registers, link registers and F pointers unchanged.

Instruction and data requests remain stable through stalls and retain response
ownership until completion. CPU and fabric reset share a cancellation contract. The
synchronous word SRAM registers reads before fetch-word selection and maps to FPGA
block RAM. Constant profile guards remove disabled multiplier, bit and CSR
datapaths; setting an illegal flag alone had retained unwanted hardware.

Emulator and RTL agree on CSR permissions, reserved IDs, trap PC/value, timer
comparison and retirement. Address arithmetic wraps explicitly at XLEN. Emulator SC
checks both reservation address and width, and vector transfers validate the full
range before modifying state. Assembler recursion and allocation limits, ELF offset
and relocation checks, and lossless reserved-byte disassembly address the toolchain
findings in the [audit](AUDIT.md).

## Tools and firmware

The SDK builds seven C++23 tools: `mica-as`, `mica-ld`, `mica-dis`, `mica-run`,
`mica-objdump`, `mica-nm` and `mica-objcopy`. They support separate assembly
compilation, nine relocation types, local/global/weak symbols, executable loading,
inspection and binary/HEX conversion. The [ELF
format](../toolchain/OBJECT_FORMAT.md) uses one image section and an experimental,
unassigned machine identifier. The CLI debugger provides stepping, breakpoints,
watchpoints and state inspection.

The three-file startup/application/library example clears BSS, computes CRC-32 and
prints through UART. Other checked programs cover RAM and arithmetic, GPIO and timer
interrupts, two-task preemption, signed 16-bit FIR filtering and a bounds-checked
software copy helper. Independent Python calculations check FIR outputs and the
emulator CRC device.

The HDL additions include synchronous Verilog SRAM, a Verilog-2005 UART receiver and
FIFO, a VHDL CRC-32 engine and a transactional SystemVerilog CRC adapter. GHDL tests
the VHDL natively and converts it to Verilog for SoC simulation. Both word-size SoCs
pass CRC, three receive interrupts and serial-pin echo. The existing VHDL watchdog
also delivers an interrupt through this integration flow.

## Regression results

| Check | Recorded result |
| --- | --- |
| Complete local runner | 20 stages passed |
| GCC Release CTest | 7 of 7 groups passed |
| Clang Debug ASan/UBSan CTest | 9 of 9 groups passed |
| ELF libFuzzer | 10,000 seeded executions passed |
| RTL/reference comparison | 1,485 runs: 250 MICA32 and 245 MICA64 programs, three memory-delay seeds |
| Additional control tests | Six reset replays, four IRQs during memory waits and 12 profile programs passed |
| Published assembly examples | 27 assemble; 24 execute under the reference emulator |
| Separate compilation | Startup, application and library link and execute |
| Compatibility | All 14 fixture hashes, register results and outputs match the recorded r1 baseline |

The macros fragment, endless LED blinker and external-watchdog wait image have
special execution requirements. The watchdog has its own SoC test. The original
comparison against an external v0.1 SDK is skipped because that SDK is absent. The
final local regression has no failing test groups. Implementation commit `4e57212`
also passed all seven [GitHub CI jobs](results/ci.json), including Linux GCC/Clang,
macOS Clang, sanitizers and the hardware flow.

The engineering suite includes 14 test cases, every possible short halfword in
disassembly round trips, and randomized long encodings. Verilog tests cover all UART
byte values, adjacent frames, false starts, framing/break recovery and reset; FIFO
simulation checks 8,000 operations. Native VHDL CRC tests use the standard check
vector and an independent 256-byte reference, then exercise busy, clear and reset.
The CRC adapter tests held responses, stalls and invalid accesses.

Formal checks cover all-input combinational ALU equivalence, response ownership and
stability for a small SRAM, and FIFO ordering/occupancy through 16 sampled clocks.
The FIFO check is bounded; induction has not closed with the current
observable-state assertions. The [formal guide](../verification/FORMAL.md) records
assumptions and scope. LeakSanitizer ran with process inspection available; sandbox
startup restrictions were resolved without disabling checks.

## Fetch and ALU experiments

With identical firmware and five deterministic memory-delay seeds, fetch-word reuse
reduced CRC-32 median cycles from 6,837 to 5,276. Instruction transactions per
retirement fell from 1.012 to 0.596. The copy example fell from 757 to 595 median
cycles. [Raw runs](results/fetch-results.json) retain both configurations.

The standalone segmented adder used 244 generic six-input LUTs, compared with 243
for the conventional unit. For 10,000 vectors, 90% narrow, upper adder-result
transitions were 30,104 and 160,682 respectively. The [activity
report](../research/POWER.md) explains the stable-value RTL measurement. Routed
timing and energy remain to be measured, and the main 64-bit core still uses its
conventional arithmetic path.

## Mapped resources

Yosys mapped the following 4 KiB SoCs to Xilinx 7-series primitives:

| Configuration | LUTs | Flip-flops | DSP48 | RAMB36 |
| --- | ---: | ---: | ---: | ---: |
| MICA-C | 4,499 | 983 | 0 | 1 |
| MICA-E | 6,198 | 1,508 | 6 | 1 |
| MICA-64 | 14,782 | 2,885 | 23 | 2 |
| MICA-E with RX/FIFO and VHDL CRC | 6,580 | 1,823 | 6 | 1 |

All include UART TX and GPIO. C disables PERF/T/M/F/B; E and 64 enable PERF and
their manifest extensions. Standalone 64 KiB, 32-bit SRAM maps to 16 RAMB36.
[Complete counts and logs](results/synthesis/results.json) preserve the mapping
configuration. The reference core's area is a clear target for further work.
Post-route frequency, vendor power analysis and external-core comparisons are still
pending.

## Host emulator throughput

The counted-loop benchmark ran five million iterations, three repetitions, on an
Intel Core i7-9700 with Linux and a GCC 15.2.1 Release build:

| Guest width | Reference MIPS | Fast interpreter MIPS | Specialized loop MIPS |
| --- | ---: | ---: | ---: |
| 32 | 29.9 | 54.5 | 1,012.4 |
| 64 | 30.2 | 56.2 | 974.6 |

These medians describe one guest loop. The short specialized runs include
process-launch overhead and visible variation; that engine handles a specific
counted-loop shape. [Raw repetitions](results/emulator-results.json) include host
identity and elapsed time. They measure host emulation throughput rather than a
physical MICA clock. The earlier EPYC report belongs to r1.

## FPGA and release validation

The actual `mica_arty_a7` top passes simulation with a 100 MHz input, 4 KiB SRAM,
RX/CRC enabled and synchronized reset release. The test checks timer handling,
GPIO/halt/fault LEDs and the serialized self-test message. Vivado implementation,
post-route timing, physical programming/boot and power measurements remain pending.
The [board guide](../hardware/FPGA_BUILD.md) separates these stages.

Drawings provide editable DOT sources, SVG/PDF previews and checked RTL nets and
module connections. Arty package pins come from the vendor documentation. They
describe the CPU and board integration; the project has no custom PCB or ASIC
physical implementation.

The binary SDK and repeatable source archive are written under `build/releases`.
[Release checks](results/release.json) cover installed tools, both word sizes,
linked startup/library firmware, peripheral input, source checksums and a clean
extracted-source build. The source archive retains historical binaries as
compatibility fixtures; the binary SDK contains the current tools.

## Remaining work

The performance pipeline, general JIT/compiler backend, independent ELF
sections/debug metadata and richer parser diagnostics are still open. Hardware
currently supports one uncached hart in machine mode. User protection, multicore
synchronization, atomic/SIMD RTL, a general RTOS runtime and a C library need
further implementation. MICA-MP remains unavailable in profile selection; MICA-DSP
is an emulator configuration.

The next priorities are to reduce reference-core area, extend long-encoding and
CSR/interrupt coverage, build the pipeline against the retirement oracle, and
complete Vivado/board bring-up. Shared execution units and narrower counters are
candidates for area experiments. Register banking, event queues and hardware loops
need their own cost and context-state measurements. Equivalent external cores can
then be compared with matched memory, clock and implementation flows.
