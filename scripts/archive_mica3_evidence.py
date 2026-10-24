#!/usr/bin/env python3
"""Archive the executed 3.0 development regression and matched prior baseline."""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--build-dir", type=Path, default=ROOT / "build/verify-v3")
parser.add_argument("--sanitizer-log", type=Path, default=ROOT / "build/san-v3.log")
parser.add_argument(
    "--output", type=Path, default=ROOT / "docs/engineering/results/mica3-r1"
)
args = parser.parse_args()
build, out = args.build_dir.resolve(), args.output.resolve()
regression = json.loads((build / "validation/results.json").read_text())
required = {
    "software",
    "hdl",
    "lint",
    "differential",
    "differential-mica2",
    "multiply-oracle",
    "instruction-matrix",
    "compiler-rtl",
    "sensor-demo",
    "fault-injection",
    "formal",
    "synthesis",
    "v3-schematics",
    "compiled-density",
    "instruction-mix",
    "control-density",
}
if not required <= {row["name"] for row in regression} or any(
    row["exit"] for row in regression
):
    raise SystemExit("a complete successful --all regression is required")
sanitizers = args.sanitizer_log.read_text()
if "100% tests passed" not in sanitizers:
    raise SystemExit("a successful sanitizer CTest log is required")
out.mkdir(parents=True, exist_ok=True)
files = {
    build / "validation/results.json": "regression.json",
    build / "validation/ctest.xml": "ctest.xml",
    build / "compiler-rtl/results.json": "compiler.json",
    build / "instruction-matrix-rtl/results.json": "instructions.json",
    ROOT / "build/multiply-tests/results.json": "multiply.json",
    ROOT / "build/sensor-demo/results.json": "sensor.json",
    ROOT / "build/fault-injection/results.json": "faults.json",
    ROOT / "build/compiled-density/results.json": "compiled-density.json",
    ROOT / "build/control-density/results.json": "control-density.json",
    ROOT / "build/instruction-mix-v3.json": "instruction-mix.json",
    ROOT / "build/synthesis/results.json": "synthesis.json",
    ROOT / "build/differential/results.json": "differential.json",
    ROOT / "build/differential-mica2/results.json": "differential-mica2.json",
    ROOT / "build/differential-parity/results.json": "differential-parity.json",
    ROOT / "build/profile-tests/results.json": "profiles.json",
    args.sanitizer_log: "sanitizers.log.gz",
    ROOT / "build-san/Testing/Temporary/LastTest.log": "sanitizer-details.log.gz",
    ROOT / "docs/hardware/schematics/v3/validation.json": "schematics.json",
    ROOT
    / "docs/engineering/results/embedded-r3/synthesis.json": "baseline-synthesis.json",
    ROOT
    / "docs/engineering/results/embedded-r3/compiled-density.json": "baseline-compiled-density.json",
    ROOT
    / "docs/engineering/results/embedded-r3/compiler.json": "baseline-compiler.json",
    ROOT / "docs/engineering/results/embedded-r3/sensor.json": "baseline-sensor.json",
}
for path in (build / "validation").glob("*.log"):
    files[path] = "logs/" + path.name + ".gz"
for path in (ROOT / "build/formal").glob("*.log"):
    files[path] = "formal/" + path.name + ".gz"
for name in ("sensor-demo", "fault-injection", "compiled-density", "control-density"):
    files[ROOT / "build" / name / "commands.log"] = name + ".log.gz"
for source, name in files.items():
    data = source.read_bytes()
    target = out / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(data, mtime=0) if target.suffix == ".gz" else data)

inputs = sorted(
    {
        *ROOT.glob("rtl/**/*.sv"),
        *ROOT.glob("rtl/**/*.v"),
        *ROOT.glob("rtl/**/*.vhd"),
        *ROOT.glob("compiler/**/*.py"),
        *ROOT.glob("compiler/**/*.c"),
        *ROOT.glob("toolchain/**/*.cpp"),
        *ROOT.glob("toolchain/**/*.hpp"),
        *ROOT.glob("isa/**/*.json"),
        ROOT / "release.json",
        ROOT / "sim/emulator.cpp",
        ROOT / "schematics/v3_sheets.py",
        ROOT / "scripts/generate_v3_schematics.py",
    }
)
environment = {
    "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "baseline_commit": "d29511c7e35dc37852792cd9c4ad3c70a3caabe2",
    "release": json.loads((ROOT / "release.json").read_text()),
    "source_head_before_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip(),
    "source_sha256": {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in inputs
    },
}
for name, command in {
    "gcc": ["g++", "--version"],
    "clang": ["clang", "--version"],
    "verilator": ["verilator", "--version"],
    "ghdl": ["ghdl", "--version"],
    "yosys": ["yosys", "-V"],
    "llvm_mc": ["llvm-mc", "--version"],
}.items():
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    environment[name] = result.stdout.splitlines()[0]
(out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
index = "# MICA 3.0 development r1 evidence\n\n"
index += "Executed local regression, raw logs and matched 2.0 r3 records. The baseline is d29511c; current source hashes and tools are in environment.json. Tests establish their recorded scope and do not establish pipeline, security, physical energy, routed timing or board qualification.\n\n"
index += "Reproduce with scripts/verify.py --all --build-dir build/verify-v3, run the sanitizer CTest suite, then scripts/archive_mica3_evidence.py. The archiver rejects partial or failed regressions. Historical baseline records retain their original source and measurement scope.\n\n"
index += "| File | Contents |\n| --- | --- |\n"
for name in sorted(files.values()):
    index += f"| [{name}]({name}) | {'Raw log' if name.endswith('.gz') else 'Executed results or baseline record'} |\n"
index += "\n[Environment and source hashes](environment.json), [engineering report](../../MICA3_DEVELOPMENT.md).\n"
(out / "README.md").write_text(index)
print("PASS archived executed 3.0 results:", out)
