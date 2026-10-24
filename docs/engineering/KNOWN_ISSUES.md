# Known implementation gaps

These issues remain open after development r3. Passing simulations do not close
the broader acceptance gates.

| ID | Gap | Required evidence to close |
| --- | --- | --- |
| C-01 | C translation supports a restricted unoptimized IR subset | Maintained target backend, broader language/ABI suite and optimization validation |
| C-02 | Significant spill traffic and large complete firmware | Register allocation across blocks, lowering/relaxation improvements and matched full-program measurements |
| C-03 | No XLEN64 C target, aggregate ABI, varargs or C++ runtime | Specified ABI and compiler/runtime conformance |
| ELF-01 | Sections share a materialized SRAM image | Independent relocatable sections, NOBITS, ROM/RAM layout and startup tests |
| CPU-01 | No pipelined implementation | RTL and retirement equivalence for hazards, stalls, branches, traps and reset |
| CPU-02 | No finite transaction timeout | Fabric contract, precise timeout behavior and non-idempotent peripheral tests |
| ISA-01 | A/V hardware missing | Integrated atomic ordering/vector execution and conformance before profile promotion |
| REL-01 | SRAM, PC and CSRs lack integrity storage | Protected implementations and exhaustive/sampled fault campaigns with stated coverage |
| REL-02 | Register parity is fail-stop only | Independent restart/reset policy and protected diagnostics; even-bit errors remain a limitation |
| SEC-01 | No memory isolation or secure boot boundary | Privilege/permission RTL, explicit trust model, authentication and negative tests |
| POWER-01 | No physical clock gate or energy result | Clock/reset implementation, activity-to-power flow and physical measurements |
| FPGA-01 | Board and routed timing unverified | Vivado implementation reports and physical boot/peripheral evidence |
| BENCH-01 | Competitor images built but not target-executed | Equivalent workload execution, matched memory assumptions and cycle/area/energy evidence |

Fixed regressions are traced to `tests/isa_contract.py` (ISA/tool integration,
signed flow, proposed profiles and peripheral wake), `compiler/tests/run.py`
(constant pointers, narrow values, calls and preservation), the native/converted
watchdog tests, `verification/differential/mica2.py` (fetch invalidation and precise
faults), and strict generated-artifact/source checks in CI.
