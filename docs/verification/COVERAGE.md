# Coverage limits

Retirement tests exercise base scalar, M/F/B, XLEN64 W/memory, X registers, T
entry/return, reserved opcodes and malformed field combinations. Independent
reference calculations cover scalar/bit/vector arithmetic and scalar FIR. The
disassembly round-trip stream includes all 65536 halfwords plus random long
encodings, but a round trip by itself is not an execution test.

Open gaps include exhaustive long encoding legality, all CSR transitions, formal CPU
retirement, every interrupt arrival point, bus reset races after non-idempotent
peripheral writes, vector hardware, multicore ordering and pipeline hazards.
Protected task isolation, FPGA clock corners and physical-board boot are untested.
Coverage percentages require an instrumented coverage database.

The generated [instruction matrix](INSTRUCTION_MATRIX.md) executes one explicit
case per allocated instruction and supported XLEN, then compares scalar retirement
under three bus-stall seeds. These vectors establish integration, not exhaustive
semantics. A/V remain software-only. Signed-flow boundary/fault tests, self-modifying
parcel tests, compiled C programs, watchdog integration and targeted register/FSM/
PC/fetch injection supplement those vectors. Register parity is also exercised
through the scalar differential suite. SPI has bounded protocol/completion checks.
