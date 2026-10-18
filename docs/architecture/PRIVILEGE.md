# Execution mode

MICA r2 implements one machine execution mode. There is no user/supervisor
mode, MPU, virtual memory, process isolation or security boundary between
firmware tasks. All implemented CSR access rights still apply: reserved and
read-only writes fault. T prevents nested trap entry until eret.

The demonstration scheduler preserves registers but runs trusted machine
code. Do not use its existence as evidence of protected multitasking or
RTOS readiness. Adding user mode requires an architectural state bit, CSR
permission checks in both engines, memory access checks and new differential
fault tests before the capability can be advertised.
