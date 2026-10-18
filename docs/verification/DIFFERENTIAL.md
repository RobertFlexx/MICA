# Architectural retirement comparison

The RTL exposes trace_valid, trace_order, trace_pc, trace_insn, trace_length,
trace_retired, trace_trap, trace_cause, trace_next_pc, trace_regs and scalar memory
event signals. trace_regs is sixteen XLEN slices, x0 first; unsupported X registers
are zero. Memory reports the effective address, byte count, read/write direction and
unshifted low access data. F updates both destination and base before its single
event. An interrupt has length=0/insn=0 and no retirement. A synchronous fault has
no committed memory event. T ecall retires with trap cause 11.

The emulator's --retire-trace JSONL adds the previous full register snapshot. The
Verilator driver emits the same common fields and the Python harness stops on the
first field mismatch, reporting event, PC and artifact paths. Full register
snapshots capture writes of identical values as state equality; an explicit
per-source read-port record is not provided. This is MICA's own trace format, not
RVFI or RISC-V binary compatibility.

The driver holds responses, randomizes request acceptance and response delays,
checks stalled request stability, and drops outstanding ownership on joint reset.
Compatibility-mode tests include successful programs, reserved R opcodes 31..255, odd jumps,
read/write/fetch faults, invalid CSRs and software/external interrupts. External IRQ
is injected during delayed store/load transactions and compared at their following
architectural boundary. Reset replays exercise clean restart.

Counter/timer values are platform-clock dependent and are not normalized away in
arbitrary traces: differential workloads avoid reading physical cycle/timer values.
Timer/scheduler behavior is checked against expected outcomes separately in emulator
and SoC, because clock ticks and functional steps differ. Tracing turns off
fast/native dispatch; optimized-engine behavior is checked separately by the
fast-path suite.

The 2.0 suite, `verification/differential/mica2.py`, uses MICA-2C/2E/2L drivers
and the matching tool profiles. It checks all stack slots, SP aliases, address
wrap, x0 loads, branch displacement limits, counter wrap, ADRPC signed limits,
high registers, F copy loops, signed word loads, illegal fields and precise
faults. Delayed external wake checks that sleeping WFI issues no requests or
extra retirement; T-enabled delivery and handler return are compared separately.
Timer outcomes are checked by the SoC bench rather than comparing unlike clocks.
