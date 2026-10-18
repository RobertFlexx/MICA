# Formal scope and assumptions

`python3 scripts/run_formal.py` runs SBY with Yosys and Z3 and archives logs.
`add64.sby` proves all combinations of 64-bit operands, add/sub, enable and narrow
selection produce identical conventional/segmented outputs.

`sram.sby` proves the 64-byte instantiation's response ownership, stability
under backpressure and reset clearing. The first sampled cycle is assumed to be
reset. Subsequent inputs/reset are unconstrained. Responses are checked without
assuming request fairness or eventual response acceptance. Same-address cross-port
data collision values are outside the memory contract; the properties do not assert
a collision value.

Logs include base-case/induction status and engines. The runner uses a 60-second
timeout and fails on timeout/error. SBY working paths are staged without spaces
to accommodate its shell invocation behavior.

Verilator differential builds also enable simulation assertions for x0, stable
stalled requests, illegal-instruction nonretirement and distinct F write
destinations.

`fifo.sby` checks all input sequences through 16 sampled clocks for a depth-three,
four-bit circular FIFO against a shift-register queue. Only the first cycle is
assumed reset; payloads, requests and later resets are unconstrained. This is a
bounded check of ordering, occupancy and simultaneous replacement. It is not an
inductive FIFO proof: head-only observable assertions do not constrain all hidden
payloads strongly enough for induction. The deterministic simulation adds 8,000
queue operations across wrap and reset.

Formal coverage is limited to these components. Whole-core retirement, atomics,
privilege, pipelines and cache coherence require separate proofs.
