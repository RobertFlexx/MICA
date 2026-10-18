# Engineering revisions

MICA's instruction-set version remains 1.0. Engineering revisions identify
compatible implementation and tooling changes. Revision r2 introduces the
transactional reference core, ELF image tools and expanded verification.

The [change log](../CHANGELOG.md) lists release changes. The [implementation
report](engineering/IMPLEMENTATION_REPORT.md) records validation and current limits.
[Compatibility fixtures](../isa/compatibility.json) preserve existing firmware bytes
and expected behavior; reserved encodings and invalid accesses have the corrected
semantics described in the ISA manual.
