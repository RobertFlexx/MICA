# Design experiments

## Upper-half arithmetic isolation

A 64-bit datapath often executes operations that only need 32 bits. The segmented
add/sub unit tests whether isolating its high operands and carry can reduce
upper-half activity while preserving the architectural result. The baseline is a
conventional 64-bit unit with the same enable and narrow-result semantics. Both
implementations are in `rtl/mica_add64.sv`.

For 10,000 deterministic vectors, 90% narrow, the upper adder-result transition
counts were 160,682 for the conventional unit and 30,104 for the segmented unit.
Generic six-input LUT mapping used 243 and 244 cells respectively. Simulation and an
all-input combinational proof agree on results.

Operand isolation reduces the measured RTL activity for this input mix at roughly
equal mapped LUT count. Routed timing and energy still need measuring. The units are
standalone experiments; the main 64-bit core uses its existing arithmetic path.
[Activity methodology](POWER.md) describes what the transition counts include.

## Fetch-word reuse

The reference core can retain one aligned 32-bit instruction word and reuse its
halfwords. The experiment compares `FETCH_REUSE=0` and `FETCH_REUSE=1` on the same
firmware, with five fixed memory-delay seeds and identical retirement traces.

For CRC-32, reuse reduced median simulated cycles from 6,837 to 5,276 and
instruction transactions per retirement from 1.012 to 0.596. The copy example fell
from 757 to 595 median cycles. This establishes a reduction in fetch work under the
tested memory model. The buffer's additional control cost and SRAM energy per
transaction are separate questions. [Raw
runs](../engineering/results/fetch-results.json) include every seed and both
configurations.

## Buffer bounds in software

`stdlib/bounded32.mica` checks destination and source end pointers and addition
overflow before calling the F copy routine. Bounds are ordinary register values, so
there is no extra context state to save. Tests cover accepted ranges, rejected
ranges and an unchanged destination after rejection.

The helper provides a baseline for bounded streaming research. Interrupts can
observe a partially completed valid copy, and a later memory fault leaves previous
stores in place. Its contract excludes MMIO and concurrent buffer mutation. Hardware
bounds would need per-access fault rules and measured cost before a new instruction
allocation is useful.

## Further experiments

The timer scheduler provides a software save/restore baseline for register-bank
research. Hardware banking adds storage and context-selection logic, so its latency
improvement needs to be weighed against register-file area and leakage. A hardware
loop controller similarly adds state that must survive interrupts. Neither mechanism
has an implemented r2 hardware experiment.

Queued peripheral events and parallel versus shared-lane SIMD are also open work.
The former needs a defined timestamp, overflow and deadline policy; the latter needs
numerical RTL tests and comparable synthesis configurations.
