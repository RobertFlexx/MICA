# Exceptions and precise retirement

| Cause | Event | TVAL |
| ---: | --- | --- |
| 0 | odd instruction target/fetch address | target/address |
| 1 | instruction access failure | failed parcel address |
| 2 | illegal encoding, absent extension, invalid CSR or eret | raw byte-image instruction bits |
| 4 | misaligned load | effective address |
| 5 | failed load response/unmapped load | effective address |
| 6 | misaligned store | effective address |
| 7 | failed store response/unmapped store | effective address |
| 11 | T ecall | zero |

For synchronous faults EPC is the faulting instruction's PC. No register write, flow
base update or store effect may commit. Faults do not retire. For legacy T ecall,
EPC is sequentialPC and the instruction does retire. MICA 2.0 ecall instead saves
the faulting instruction PC; the handler must advance EPC to skip it. The ecall
retirement event still carries trap cause 11. Entry copies IE to previous IE,
clears IE, sets handler-active and redirects to TVEC. No general register is saved
by hardware. Firmware owns its stack frame.

Eret requires active T state and an even EPC. It restores PC=EPC, IE=previous IE,
clears previous IE and handler-active, and retires. A missing/invalid vector, an
exception inside an active handler or T-disabled fault terminates with a fault
indication. Nested recovery is not implemented. Breakpoints in the CLI are debugger
stops, not an allocated architectural breakpoint opcode.

A jump to even unmapped memory retires before its subsequent fetch faults. An odd
jump faults before writing LR. The retirement stream exposes trap and normal
completion separately. Stores that return error must have no memory side effect, as
required by the memory-interface contract.
