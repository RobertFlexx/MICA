# Pipeline work

The MICA 2.0 CPU is a multicycle reference core. It separates pending effects
from commit for precise retirement and executes one instruction at a time.
The legacy core module adapts its external interface to this implementation.

A three-stage pipeline is the next microarchitecture candidate. The main design
questions are dependency handling, forwarding both F writes, load-use stalls,
branch/trap redirects and memory-response ownership. Its retirement stream can use
the existing differential harness, so timing changes can be checked against the
reference before performance comparisons.

Current [hardware benchmarks](../../benchmarks/hardware.py) report cycles and IPC
for the multicycle core under specified memory delays. A pipelined implementation
and its throughput measurements are still open work.
