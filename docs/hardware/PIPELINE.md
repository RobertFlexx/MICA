# Pipeline status

There is one verified CPU microarchitecture in r2: the multicycle reference.
Its pending-effect/commit separation supplies precise retirement but does not
execute multiple instructions concurrently. The legacy core is an interface
adapter around this core, not a second performance implementation.

A three-stage performance implementation remains unfinished. Required work is
fetch/decode/retirement validity, same-register hazards, two-write F forwarding,
load-use stalls, branch/trap flushing, response ownership and a common trace.
Any future IPC claim must come from the checked workload harness. Current
`benchmarks/hardware.py` reports measured reference-core cycles and IPC under
specified memory delays. It does not approximate one-instruction-per-clock.
