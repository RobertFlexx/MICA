# Formal scope and assumptions

`python3 scripts/run_formal.py` runs SBY with Yosys and Z3 and archives logs.
`add64.sby` proves all combinations of 64-bit operands, add/sub, enable and
narrow selection produce identical conventional/segmented outputs. It is a
combinational equivalence proof, not a power or CPU proof.

`sram.sby` proves the small64-byte instantiation's response ownership,
stability under backpressure and reset clearing. The first sampled cycle is
assumed to be reset. Subsequent inputs/reset are unconstrained. Responses are
checked without assuming request fairness or eventual response acceptance.
Same-address cross-port data collision values are outside the memory contract;
the properties do not assert a collision value. No global processor, atomic,
privilege, pipeline or cache-coherence proof has been completed.

Logs include base-case/induction status and engines. The runner uses a 60-second
timeout and fails on timeout/error. It does not treat bounded PASS as proof of
an entire processor. SBY working paths are staged without spaces to accommodate
its shell invocation behavior.

Verilator differential builds also enable simulation assertions for x0,
stable stalled requests, illegal-instruction nonretirement and distinct F write
destinations. These runtime assertions are not presented as formal CPU proofs.

`fifo.sby` checks all input sequences through 16 sampled clocks for a depth-three,
four-bit circular FIFO against a shift-register queue. Only the first cycle
is assumed reset; payloads, requests and later resets are unconstrained. This
is a bounded check of ordering, occupancy and simultaneous replacement. It is
not an inductive FIFO proof: head-only observable assertions do not constrain
all hidden payloads strongly enough for induction. The deterministic simulation
adds 8,000 queue operations across wrap and reset.
