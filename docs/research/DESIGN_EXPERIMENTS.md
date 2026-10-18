# Implemented experiments and pending research

## Segmented arithmetic

Hypothesis: isolating the upper half during 32-bit operations reduces upper-lane
activity. Baseline is a conventional64-bit add/sub unit with the same enable
and narrow semantics. Implementation is two32-bit adders with explicit carry
and upper operand isolation. The10000-vector benchmark and an all-input formal
proof establish equal results. Archived measurements compare LUT count and RTL
transitions. Conclusion: upper RTL transitions decrease on this input mix;
physical energy/timing benefit is unproven. Both units are standalone.

## Fetch reuse

Hypothesis: one retained aligned32-bit word reduces halfword fetch transactions.
Baseline sets FETCH_REUSE=0 on the same multicycle core; candidate sets1.
Both execute identical firmware with the same deterministic latency seeds and
must match the reference trace. The benchmark measures transactions, cycles
and IPC. Conclusion and exact results are recorded in the implementation report;
no memory-energy model or tight-loop cache benefit is assumed.

## Software bounds prototype

`stdlib/bounded32.mica` validates destination/source end pointers and addition
overflow before tail-calling the F copy routine. Bounds remain ordinary visible
register values. Interrupts can observe a partial valid copy; earlier stores
remain completed on a later memory fault. It excludes MMIO and concurrent buffer
mutation. This is a software baseline with tested range rejection, not an
allocated bounded-stream instruction. Hardware limits, context CSRs and
per-access fault semantics need a separate experiment and cost comparison.

## Experiments not implemented

Register-bank switching requires a measured save/restore baseline, actual bank
storage, task tests and synthesis/leakage cost. Event queues require source,
timestamp, overflow and deadline policies plus a real peripheral workload.
A hardware loop controller requires explicit context state, interrupt tests
and comparison against dbnz. Parallel and multicycle SIMD require bit-exact
RTL and numerical tests. These remain open work; no result is invented for them.
