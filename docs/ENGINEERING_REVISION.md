# Engineering revisions

MICA's current instruction-set version is 2.0. Select it with MICA2=1 or a
MICA-2 profile. MICA2=0 preserves the 1.0 compatibility decode. The
[2.0 verification report](engineering/MICA2_VERIFICATION.md) records current
software, HDL, formal and synthesis checks.

Development r2 adds optional signed F loads, instruction allocation validation,
fetch refinements and additional portable components. Development r3 improves
experimental C compilation, adds compiled sensor firmware, direct sleep interrupt
entry and optional register parity. The ISA remains version 2.0. The
[embedded report](engineering/EMBEDDED_REFINEMENT.md) distinguishes these changes
from incomplete pipeline, protection and qualification work.

The historical 1.0 engineering r2 revision introduced the transactional core,
ELF image tools and expanded verification without changing 1.0 encodings.

The [change log](../CHANGELOG.md) lists release changes. The [implementation
report](engineering/IMPLEMENTATION_REPORT.md) records validation and current limits.
[Compatibility fixtures](../isa/compatibility.json) preserve existing firmware bytes
and expected behavior; reserved encodings and invalid accesses have the corrected
semantics described in the ISA manual.
