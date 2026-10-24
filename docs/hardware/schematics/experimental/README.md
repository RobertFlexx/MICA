# Experimental hardware work

No implemented pipelined, vector, memory-protection, secure-boot, ECC or lockstep
CPU is present in this revision. The corresponding numbered implementation-status
sheets identify the gaps. A speculative circuit is not included in the
[implemented collection](../v3/README.md).

Future designs need source RTL, clock/reset and transaction contracts, precise
retirement behavior, standalone and integration tests, source-backed drawings,
mapped resources and timing evidence before promotion. DSP extensions also need
an independent numerical oracle and real compiler selection. Security work needs
an explicit threat model and implemented trust boundary. The
[architecture contract](../../../architecture/MICA3.md) records the complexity
decisions and compatibility requirements.
