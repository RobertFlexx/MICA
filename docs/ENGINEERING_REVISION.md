# Engineering revisions

MICA's current instruction-set version is 2.0. Select it with MICA2=1 or a
MICA-2 profile. MICA2=0 preserves the 1.0 compatibility decode. The
[2.0 verification report](engineering/MICA2_VERIFICATION.md) records current
software, HDL, formal and synthesis checks.

The historical 1.0 engineering r2 revision introduced the transactional core,
ELF image tools and expanded verification without changing 1.0 encodings.

The [change log](../CHANGELOG.md) lists release changes. The [implementation
report](engineering/IMPLEMENTATION_REPORT.md) records validation and current limits.
[Compatibility fixtures](../isa/compatibility.json) preserve existing firmware bytes
and expected behavior; reserved encodings and invalid accesses have the corrected
semantics described in the ISA manual.
