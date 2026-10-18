# Switching activity and power

The current power-related measurements are RTL transition counts and fetch
transactions. They identify activity changes worth investigating in a physical flow.
A capacitance, clock-tree and leakage model is still needed to estimate energy per
completed task.

## Segmented ALU

`benchmarks/alu_activity.py` applies 10,000 deterministic add/sub vectors, 90%
narrow, to both ALUs. It verifies equal results, counts stable-value transitions in
the upper 32-bit signals from VCD, and maps both units to six-input LUTs. The
[archived results](../engineering/results/alu-research/results.json) include the
seed, tool versions, mapped cell counts and signal counts.

For narrow operations, the segmented unit isolates high operands and carry; its high
sum remains zero while the architectural result sign-extends the low 32 bits. This
uses combinational operand isolation, with no clock gate. The conventional and
segmented upper-sum counts are 160,682 and 30,104.

VCD stable-value counts omit gate glitches, routing capacitance and clock/leakage
cost. Those omissions matter when converting activity into watts. The main 64-bit
core also has its own conventional arithmetic path, so this experiment measures the
standalone units rather than whole-core power.

## Fetch traffic

The fetch-reuse benchmark records fewer instruction-memory transactions on the
reference core. Its [raw runs](../engineering/results/fetch-results.json) show the
transaction and cycle changes. SRAM energy per access and the buffer's physical
implementation cost have not yet been measured.
