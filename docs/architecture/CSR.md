# MICA 1.0 CSR map

CSR IDs are unsigned aux8 in major 5. `csrr d,id` requires ra=rb=0; `csrw id,a`
requires rd=rb=0. Unsupported IDs and writes to read-only IDs raise
illegal-instruction cause 2 before side effects. Accesses execute in the
[single machine mode](PRIVILEGE.md).

| ID | Name | Availability/rights | Reset and semantics |
| ---: | --- | --- | --- |
| 0 | coreid | base R | zero, one hart |
| 1 | status | T RW bit 0 | 0; IE bit 0, previous IE bit 1, handler-active bit 2; other bits zero |
| 2 | epc | T RW | 0; even resume address |
| 3 | cause | T RW | 0; fault code or interrupt flag plus source |
| 4 | tvec | T RW | 0 disables entry; even nonzero handler address required for delivery |
| 5 | ie | T RW | 0; bits 0 and 1 writable, others zero |
| 6 | ip | T R/W bit 0 | 0; read software/external OR at bit 0, timer comparison at bit 1 |
| 7, 8 | cycle_lo, cycle_hi | base R, PERF optional | low/high 32 implementation clock/step count; zero without PERF in RTL |
| 9, 10 | timer_lo, timer_hi | T RW | 64-bit timer initially zero; each write replaces one 32-bit half |
| 11, 12 | cmp_lo, cmp_hi | T RW | 64-bit comparator initially all ones; pending if timer >= comparator |
| 13 | vec_dirty | V R, emulator | 0; any vector execution sets 1 |
| 14 | vec_enabled | V RW bit 0, emulator | 1 when V configured; zero makes vector execution illegal |
| 15 | features | base R | capability bitmap below |
| 16 | arch | base R | XLEN, 32 or 64 |
| 17, 18 | instret_lo, instret_hi | base R, PERF optional | low/high 32 successfully retired count, initially 0 |
| 19 | tval | T RW | 0; faulting address, raw instruction bits for illegal instruction, or 0 on interrupt/ecall |
| 20..255 | reserved | illegal | no storage semantics |

Feature bits: X=0, M=1, F=2, A=3, V=4, B=5, T=6, PERF=7. RTL never advertises A/V.
Emulator always provides PERF. Counts wrap modulo 2^64. CSR half reads zero extend
to XLEN even on MICA64. Read instret before retiring the csrr itself. Counter/timer
clock units are platform specific: RTL clocks include stalls; the functional
emulator advances once per attempted instruction. These values must not be compared
as physical cycle performance.

Use high/low/high retry when sampling a changing 64-bit counter on XLEN32. For timer
programming, mask timer delivery, write cmp_hi to all ones, write cmp_lo, then the
final cmp_hi and restore the mask. Timer writes need the same care. There is no
atomic pair-write instruction. Setting cmp_hi to all ones is sufficient to quiesce
the short supplied demonstrations; full wraparound applications must implement a
platform timer policy.

IP software state cannot clear the external level or timer condition. Clear software
bit 0 with csrw ip,x0. Acknowledge the peripheral or move comparison into the future
for other sources. Status writes change only IE; hardware owns previous IE and
handler-active. Odd EPC/TVEC writes are illegal and leave the previous value intact.
A vector outside configured RAM is fatal at delivery.
