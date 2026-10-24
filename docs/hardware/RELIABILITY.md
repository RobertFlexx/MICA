# Optional register integrity and fault injection

`REG_PARITY=1` on `mica_core_txn` or `mica_soc` adds one parity bit per physical
GPR. Reset initializes parity from the architectural reset values, including SP.
Successful writeback updates parity from the exact value written, including sign
extension and post-increment base updates. Default `REG_PARITY=0` removes this
logic. No ISA opcode or capability bit is added.

DECODE checks every implemented GPR before queuing effects. A mismatch asserts
`fault_o`, invalidates the fetch buffer and enters terminal STOP before that
instruction issues a data request. It is fail-stop detection, not correction or
a recoverable architectural trap. External reset or independent watchdog policy
is required to restart. A stopped core does not advance its internal timer.
The optional SoC watchdog continues ticking independently.

Odd-bit errors present at the check boundary are detectable. Even-bit errors,
corruption overwritten before a check, memory errors and corrupted parity/checker
logic are outside that guarantee. CSR, PC and SRAM have no parity protection.
The implementation is not a lockstep processor or a safety-qualified design.

`scripts/test_fault_injection.py` injects one error per reset at a WFI boundary.
It sweeps all 32 bits of x1 and one SRAM word, with parity disabled/enabled. It
also tests one invalid controller state, odd PC, and an instruction response error.
The campaign records expected silent corruption in unprotected state. This
targeted set is not a probability estimate for random physical faults.

An invalid FSM state takes the existing `fault_o`/STOP path. Odd PC and fetch
access errors use precise architectural traps. The tests check that these cases
produce no GPIO write. Registers and memory are injected through simulation
hierarchy; no fault-injection control is exposed in deployed RTL.

Memory parity/ECC, register correction, CSR integrity, reset-cause retention,
brownout circuitry, memory protection, lockstep and qualification remain open.
MICA-2R is a proposed profile; optional parity and watchdogs do not complete it.
