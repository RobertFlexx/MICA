# Coverage limits

Retirement tests exercise base scalar, M/F/B, XLEN64 W/memory, X registers, T
entry/return, reserved opcodes and malformed field combinations. Independent
reference calculations cover scalar/bit/vector arithmetic and scalar FIR. The
disassembly round-trip stream includes all 65536 halfwords plus random long
encodings, but a round trip by itself is not an execution test.

Open gaps include exhaustive long encoding legality, all CSR transitions, formal CPU
retirement, every interrupt arrival point, bus reset races after non-idempotent
peripheral writes, vector hardware, multicore ordering and pipeline hazards.
Protected task isolation, all FPGA clock corners and physical-board boot have no
coverage because those paths are not implemented or not available. No coverage
percentage or verification closure is claimed without an instrumented coverage
database.
