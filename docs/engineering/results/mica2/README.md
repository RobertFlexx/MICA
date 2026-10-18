# MICA 2.0 verification evidence

These reports cover the MICA 2.0 source hashes recorded in `environment.json`.
The parent directory's r2 artifacts cover MICA 1.0.

[regression.json](regression.json) retains each executed stage command, exit
status and elapsed time. [environment.json](environment.json) records the
UTC execution time, tool versions, host platform and verified source hashes.
The `logs` directory contains deterministic gzip copies of the raw stage logs.

[2.0 retirement results](differential-mica2.json) record 129 ordinary runs;
nine additional reset replays are reported in the log.
[Legacy results](differential-legacy.json) retain the compatibility campaign.
[Code-size results](riscv-density.json) include MICA and RISC-V assembly sources,
emitted byte counts, and RISC-V instruction encodings.
[Synthesis results](synthesis/results.json) retain all seven profile mappings and
their primitive counts; per-profile JSON and compressed logs sit beside them.
[Fetch results](fetch-results.json) and [ALU results](alu-results.json) record
activity and simulated cycles.

Regenerate with `scripts/verify.py --all`, followed by
`scripts/archive_mica2_evidence.py`. The archiver rejects failed or incomplete
regressions. Physical FPGA tests, routed timing, electrical power and cross-ISA
hardware performance are outside this archive's scope.

The successful ASan/UBSan/fuzz run is in `logs/sanitizers.log.gz`.
`logs/sanitizers-lsan-unavailable.log.gz` retains the initial LeakSanitizer
startup failure caused by restricted process inspection. The successful run
uses `ASAN_OPTIONS=detect_leaks=0`; it provides no leak-detection result.
