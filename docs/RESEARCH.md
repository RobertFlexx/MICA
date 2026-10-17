# MICA research dossier: prior work, design choices, measurement plan

All links below lead to public primary project/specification sources. The sources are used to *inform* design choices rather than copied into the codebase or used to claim MICA surpasses its predecessors.

## A. Closest competing ISA ideas

1. **RISC-V RV32E / RV64E**: official ratified embedded bases use **16 scalar registers** rather than 32. MICA's eight-register mandatory model could shrink a register file and its switching capacitance, but adds more reload/spill overhead for compiler-generated code. That tradeoff must be measured on real workloads. https://docs.riscv.org/reference/isa/unpriv/rv32e.html
2. **RISC-V C extension**: 16-bit compressed instructions intermix with 32-bit instructions, improving code density. MICA's 16-bit-first approach is **not novel by itself**, and cannot assume an instruction-size advantage over C/Zc-compressed RISC-V. https://docs.riscv.org/reference/isa/v20260120/unpriv/c-st-ext.html
3. **RISC-V RV64I 'W' operations**: explicit 32-bit operations within 64-bit registers, with sign-extended results, offer a grounded model for MICA `addw3`, `subw3`, etc. MICA does not share their binary encodings. https://docs.riscv.org/reference/isa/unpriv/rv64.html
4. **RISC-V V extension**: configurable vector lengths and grouping permit broad scalable code. MICA opts for a fixed 128-bit narrow extension to simplify a small controller's vector state, accepting lower scalability and less general compiler vectorization. https://docs.riscv.org/reference/isa/unpriv/v-st-ext
5. **Arm Helium (MVE)**: shows the utility of embedded DSP/ML-focused SIMD, including predication. MICA's current V lacks Helium-like predication, DSP widening accumulators and sophisticated vector-memory semantics; this gap is deliberate and may hurt real workloads. https://www.arm.com/technologies/helium

## B. Existing small CPU implementations

6. **lowRISC Ibex**: mature parametric RISC-V MCU core with 2-stage pipeline and optional writeback third stage. Its design/verification culture is the comparison target: documentation, hardening, CI, integration and silicon experience. https://github.com/lowRISC/ibex and https://github.com/lowRISC/ibex/blob/master/doc/03_reference/pipeline_details.rst
7. **SERV bit-serial RISC-V**: a reminder that very low area can be achieved with established RISC-V by doing less work per cycle. MICA needs to compare against serial *and* conventional integer cores depending on area/throughput goal. https://github.com/olofk/serv
8. **RISC-V RVWMO formal memory model**: a caution against vague statements about atomic instructions ensuring multicore safety. MICA-A currently has too little formalization to make a strong compatibility or coherence claim. https://docs.riscv.org/reference/isa/unpriv/rvwmo.html
9. **Yosys and nextpnr**: open synthesis and FPGA place-and-route flows for supported families. Physical area/power assertions should come from actual synthesis/place-and-route + device measurements, not RTL line counts or instruction count. https://github.com/YosysHQ/yosys and https://github.com/YosysHQ/nextpnr

## C. Research hypothesis, not marketing

**Hypothesis H1:** An eight-register 16-bit-first mandatory ISA paired with very small control logic has lower idle/leakage and dynamic switching than an equally featured RV32E compressed implementation, *on a tightly controlled target and workload*. Counter-hypothesis: fewer registers induce enough spills and extra cycles that **total joules/task rise**.

**Hypothesis H2:** Fixed-128 SIMD with 8 registers gives favorable joules/sample on embedded FIR/audio/quantized-ML workloads versus scalar MICA and scalar RISC-V. Counter-hypothesis: vector register clocking, saturated/widening arithmetic and memory supply become the power bottleneck.

**Hypothesis H3:** In MICA64, using 32-bit W operations and bank/upper-half gating saves switching for narrow data without giving up 64-bit pointers; a later dual-slice core might dynamically bypass upper datapath when it is provably safe. **No automatic hardware gating implementation is supplied in v1.0.** Upper register bits must still be architecturally correct; a naive gate that drops upper carries is invalid.

**Hypothesis H4:** Simplified mandatory architectural state helps small-core task/context switches. Counter-hypothesis: memory copies caused by scarce registers dominate cycle counts, and SIMD/MPU state outweigh scalar savings.

## D. Honest benchmarking protocol

Measure on **the same FPGA model, process, clock input, IO voltage, RAM size and memory timing model** (and eventually matched ASIC PDK/library). For each core variant and baseline specify:

- Exact CPU RTL commit and configuration, synthesis/place-and-route versions, timing constraints and achieved critical path; show total LUTs, FFs, RAM blocks, DSP blocks.
- Workloads covering GPIO edge updates, interrupt response, CRC and AES software, memory copy, search/string length, 32/64-bit integer sums, software/hardware multiply/division, audio FIR, narrow-ML dot products and inter-hart queues.
- Compiler/toolchain provenance, optimization levels, identical input data and exact algorithm. MICA has no compiler yet, so **handwritten assembly comparisons are not representative of mature software ecosystems**.
- Bytes of ROM, dynamic retired instructions, cycles, steady-state throughput, **wall time per task**, energy per completed task, latency distribution/worst case and standby power.
- Current measurement: instrument *dedicated FPGA core rail if possible*, or subtract board idle power with calibration and acknowledge errors from regulators, IO and clocking. Capture voltage and current waveform, integrate `E = integral of voltage times current over time` over equal tasks and correct for baseline.
- For MICA-A, include memory litmus tests, reservation invalidation, fence order, concurrency stress and starvation bounds. For P, include trap entry, priority inversion and worst-case interrupt jitter.
- Report negative results and uncertainty. Prefer geometric mean over workload ratios rather than cherry-picking a single high-frequency case.

Record results under `benchmarks/results/` with dated JSON, binary/checksum, core commit, tool versions and complete command lines. No fabricated score chart is included in this SDK.

## E. What would constitute a breakthrough?

One defensible claim would look like: **"At 32-bit integer workloads compiled from the same source and synthesized to the same FPGA fabric with equal SRAM, MICA's median active energy per task is X% lower across N workloads while meeting an identical latency bound."** The numbers are placeholders: **X and N cannot be assigned until experimental results exist.**

A better achievement than merely improving a small soft-core's clock rate is a reproducible, independently verified design that beats prior art on *energy/latency/code size jointly* while requiring manageable compiler/runtime/tooling overhead.

## Further 1.0 sources

- Digilent, Arty A7 pin constraint reference: https://github.com/Digilent/digilent-xdc/blob/master/Arty-A7-100-Master.xdc. Onboard E3 clock, D9 reset button, H5/J5/T9/T10 green LEDs and D10 FPGA UART output.
- AMD Vivado UG901 memory inference capabilities: https://docs.amd.com/r/en-US/ug901-vivado-synthesis/Memory-Inference-Capabilities. Large FPGA memory and data port behavior need deliberate inference and timing checks.
- EEMBC, ULPMark overview: https://www.eembc.org/ulpmark/. Embedded efficiency needs sleep/wake, active power and complete workloads, not merely frequency.
- RISC-V, RVWMO specification: https://docs.riscv.org/reference/isa/unpriv/rvwmo.html. A multicore architecture must state its memory ordering rules as carefully as it states opcodes.

## Patent and novelty caution

Post-incrementing loads, counted loops, compressed instructions, SIMD execution slicing, low-power sleep states and clock gating all have extensive prior art. The particular implementation of MICA is independently encoded and written here, but the existence of a custom ISA does not establish patent novelty. A serious research paper should precisely identify a mechanism, compare it with prior art and provide reproducible measurements.
