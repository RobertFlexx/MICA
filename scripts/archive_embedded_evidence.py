#!/usr/bin/env python3
"""Archive executed embedded-r3 results without replacing historical evidence."""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--build-dir", type=Path, default=ROOT / "build/verify-r3")
parser.add_argument(
    "--sanitizer-log",
    type=Path,
    default=ROOT / "build-san/Testing/Temporary/LastTest.log",
    help="full sanitizer suite log, before any targeted reruns",
)
parser.add_argument(
    "--output", type=Path, default=ROOT / "docs/engineering/results/embedded-r3"
)
args = parser.parse_args()
build, out = args.build_dir.resolve(), args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
files = {
    build / "validation/results.json": "regression.json",
    build / "final-ctest.xml": "ctest.xml",
    ROOT / "build/final-ctest.log": "final-software.log.gz",
    build / "compiler-rtl/results.json": "compiler.json",
    build / "instruction-matrix-rtl/results.json": "instructions.json",
    ROOT / "build/sensor-demo/results.json": "sensor.json",
    ROOT / "build/fault-injection/results.json": "faults.json",
    ROOT / "build/compiled-density/results.json": "compiled-density.json",
    ROOT / "build/core-revision/results.json": "core-revision.json",
    ROOT / "build/synthesis/results.json": "synthesis.json",
    ROOT / "build/hdl-baseline/synthesis/results.json": "baseline-synthesis.json",
    ROOT / "build/san-r3.log": "sanitizers.log.gz",
    ROOT / "build/isa-contract-final.log": "isa-contract.log.gz",
    args.sanitizer_log: "sanitizer-details.log.gz",
    ROOT / "build/differential/results.json": "differential.json",
    ROOT / "build/differential-mica2/results.json": "differential-mica2.json",
    ROOT / "build/differential-parity/results.json": "differential-parity.json",
    ROOT / "build/profile-tests/results.json": "profiles.json",
}
for path in (build / "validation").glob("*.log"):
    files[path] = "logs/" + path.name + ".gz"
for path in (ROOT / "build/formal").glob("*.log"):
    files[path] = "formal/" + path.name + ".gz"
for name in ("sensor-demo", "fault-injection", "compiled-density"):
    files[ROOT / "build" / name / "commands.log"] = name + ".log.gz"
for source, name in files.items():
    data = source.read_bytes()
    target = out / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(data, mtime=0) if target.suffix == ".gz" else data)
inputs = [
    *ROOT.glob("rtl/**/*.sv"),
    *ROOT.glob("rtl/**/*.v"),
    *ROOT.glob("rtl/**/*.vhd"),
    *ROOT.glob("compiler/**/*.py"),
    *ROOT.glob("compiler/**/*.c"),
    *ROOT.glob("isa/**/*.json"),
    ROOT / "sim/emulator.cpp",
    ROOT / "toolchain/assembler.cpp",
    ROOT / "toolchain/linker.cpp",
]
environment = {
    "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "baseline_commit": "22b5571",
    "source_head_before_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip(),
    "source_sha256": {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(inputs)
    },
}
for name, command in {
    "gcc": ["g++", "--version"],
    "clang": ["clang", "--version"],
    "verilator": ["verilator", "--version"],
    "ghdl": ["ghdl", "--version"],
    "yosys": ["yosys", "-V"],
}.items():
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    environment[name] = result.stdout.splitlines()[0]
(out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
print("PASS archived executed results:", out)
