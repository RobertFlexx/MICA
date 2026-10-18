# Contributing

Read the normative ISA and audit before modifying decode or execution. MICA
stays at version 1.0. Compatible implementation changes use engineering
revisions. Do not reassign an allocated opcode or regenerate frozen firmware
fixtures to make a compatibility failure disappear.

Edit `isa/encodings/mica1.json` and `isa/profiles/profiles.json` for allocations
and profiles. Run `python3 scripts/generate_isa.py`; commit the generated
consumers. The structural validator in `isa/encoding.hpp` and the RTL decoder
must implement the same reserved-bit rules. Add a conformance case exercising
both a successful instruction and its relevant illegal/fault cases.

Run the commands in BUILDING.md that cover the change. Memory changes require
latency, response ownership, fault and reset tests. Trap changes require a
retirement comparison and a context-preservation case. Record the first
mismatching event when differential tests fail; do not mask fields until the
architectural reason for a difference is documented.

Keep source and generated drawings consistent. Avoid adding a mnemonic without
an implementation, empty utility wrappers, hardware claims based on emulator
speed, or performance claims without inputs and tool versions. Include measured
results and identify remaining uncertainty in reviews. Do not commit build
products, fuzz-generated corpus growth or host-specific paths.
