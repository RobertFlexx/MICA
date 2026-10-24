# Benchmark dashboard, development r3

Values below come from the [archived results](../engineering/results/embedded-r3/README.md).
The [engineering report](../engineering/EMBEDDED_REFINEMENT.md) gives commands,
tool versions, complete comparisons and limits. Missing metrics remain missing.

| Metric | Observed value | Scope |
| --- | --- | --- |
| Compiled sensor ROM | 1,220 bytes | Two C objects, startup, constants, data and alignment |
| Sensor execution | 53,715 clocks; 45,847 active, 7,868 asleep | Finite four-measurement SoC simulation |
| Wake entry | 1 clock maximum observed | Enabled timer pending while asleep; excludes external synchronization and stalled-memory arrival |
| Stable sleep datapath | 0 selected-signal transitions | Clock and timer continue switching; not physical power |
| Complete C ROM | MICA-2C 896; MICA-2E 920; RV32EC 244; Cortex-M0+ 208 bytes | Same C at frontend -O0; different backends; competitor images not target-executed |
| C memory requests | 335 on 2C, 149 on 2E | Array/structure/call/recursion ABI test; not a pure spill count |
| Optional parity cost | +298 LUTs, +16 flip-flops | Matched 4 KiB MICA-2E SoCs, Yosys XC7 mapping |
| Register injection | All 32 tested single-bit errors detected with parity | One register, one injection boundary; no correction |
| Unprotected SRAM injection | All 32 tested data-bit errors undetected | Explicitly recorded negative result |
| Signed dot product | 4,373 median clocks for 64 elements | Five fixed stall seeds, includes call/setup/exit; scalar baseline 6,069 |
| Instruction integration | 153 entries | Scalar RTL vectors, A/V software-only |
| Compiler differential | 28 C/profile cases | Native oracle, three emulator modes and RTL seeds |
| Maximum frequency | Unmeasured | No placement/routing evidence |
| Active/idle power, energy | Unmeasured | No capacitance, clock-tree or physical power model |
| Hard WCET / deadline guarantee | Not established | Fabric response time has no architectural finite bound |
| Cross-ISA cycles/area/energy | Not measured | Full-workload code-size baseline only |
| Register spills | Not separately instrumented | Loads/stores above include ordinary program memory |

MICA-2D/2R/2S are proposed profiles. Pipeline, memory protection, secure boot,
hardware SIMD/atomics and physical FPGA qualification remain incomplete.
