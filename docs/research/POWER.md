# Activity and power evidence

`benchmarks/alu_activity.py` runs10000 deterministic add/sub vectors,90% narrow,
with identical architectural results in both ALUs. It records stable-value
upper 32-bit transitions from VCD and maps both units to generic6-input LUTs.
Signal names, seed, counts, source and tool versions are archived. This is RTL
switching activity, with no capacitance weighting, glitch accounting, routing,
clock-tree or leakage model. It does not establish joules per task.

The segmented unit isolates both high operands and carry for narrow operations;
its upper sum stays zero during those operations while the result sign extends
low 32. There is no clock gate. Physical integrated gating, vendor power analysis
and energy measurement remain future experiments. The main64-bit core still
uses its conventional arithmetic path; these results are research units, not a
claim about whole-processor energy savings.

Fetch reuse reduces measured transactions in the reference core. SRAM energy
per transaction and additional control cost are not measured. Banked register
files, event batching and power domains have no synthesized implementation in
r2 and must not be credited with energy savings.
