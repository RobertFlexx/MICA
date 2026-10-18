# Interrupt delivery

T supports source 0 (software pending OR external level) and source 1 (timer).
Delivery is eligible when status.IE and the corresponding IE/IP bits are set. Timer
takes priority when both are pending. Cause has bit XLEN-1 set and low code 2 for
timer or 1 for source 0. EPC is the next instruction that has not executed.
Interrupt entry does not retire an instruction.

The core samples eligibility at START, with no outstanding memory transaction. An
interrupt arriving during a stalled access waits for that instruction to complete or
fault. Entry therefore remains precise; external bus latency bounds the worst-case
response time. There is no fixed cycle-latency guarantee under unbounded
backpressure. The SoC synchronizes its external IRQ through two flip-flops before
passing it to the core. The core port itself assumes synchronous input.

Handlers must acknowledge their source before eret, or delivery repeats. They save
every register they modify, including LR if calling a subroutine.
`examples/scheduler32.mica` saves x1..x7 and EPC in 32-byte frames and alternates
two trusted tasks for six timer ticks. Each task checks sentinel registers.
`examples/selftest32.mica` tests a timer handler plus UART/GPIO. The simulator
harness also injects external IRQ during a delayed store and a delayed load.

With MICA2=1, WFI retires and enters SLEEP. Raw pending events wake the core
even when interrupt masks are clear. Handler delivery still requires T,
status.IE and the matching IE bit. Without T, external irq_i wakes directly.
Legacy MICA2=0 WFI retains its terminal halt behavior. The
[2.0 tests](../engineering/MICA2_VERIFICATION.md) cover masked wake, handler
return and timer wake; STOP remains terminal until reset.
