#!/usr/bin/env python3
"""Archive successful current-revision verification without replacing 1.0 evidence."""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build/verify")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/engineering/results/mica2"
    )
    parser.add_argument("--sanitizers-log", type=Path)
    parser.add_argument("--sanitizer-constraint-log", type=Path)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    stages = json.loads((args.build / "validation/results.json").read_text())
    required = {
        "software",
        "hdl",
        "lint",
        "differential",
        "differential-mica2",
        "formal",
        "synthesis",
        "mica2-diagrams",
        "overview-diagrams",
        "riscv-density",
    }
    if not required.issubset({s["name"] for s in stages}) or any(
        s["exit"] for s in stages
    ):
        raise SystemExit(
            "a complete passing --all regression, including LLVM density measurement, is required"
        )

    def copy(source, target, compressed=False):
        data = source.read_bytes()
        path = out / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(data, mtime=0) if compressed else data)

    copy(args.build / "validation/results.json", "regression.json")
    for path in sorted((args.build / "validation").glob("*.log")):
        copy(path, "logs/" + path.name + ".gz", True)
    for source, target in [
        ("build/differential/results.json", "differential-legacy.json"),
        ("build/differential-mica2/results.json", "differential-mica2.json"),
        ("build/riscv-density/results.json", "riscv-density.json"),
        ("build/hardware-bench/results.json", "fetch-results.json"),
        ("build/alu-research/results.json", "alu-results.json"),
    ]:
        copy(ROOT / source, target)
    for path in sorted((ROOT / "build/synthesis").glob("*")):
        if path.suffix in [".json", ".log"]:
            copy(
                path,
                "synthesis/" + path.name + (".gz" if path.suffix == ".log" else ""),
                path.suffix == ".log",
            )
    for path in sorted((ROOT / "build/formal").glob("*.log")):
        copy(path, "formal/" + path.name + ".gz", True)
    versions = {}
    for command in [
        ["g++", "--version"],
        ["cmake", "--version"],
        ["iverilog", "-V"],
        ["verilator", "--version"],
        ["ghdl", "--version"],
        ["yosys", "-V"],
        ["sby", "--version"],
        ["z3", "--version"],
        ["llvm-mc", "--version"],
    ]:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        versions[command[0]] = (result.stdout + result.stderr).splitlines()[0]
    sources = sorted(
        {
            *ROOT.glob("rtl/**/*.sv"),
            *ROOT.glob("rtl/**/*.v"),
            *ROOT.glob("rtl/**/*.vhd"),
            *ROOT.glob("toolchain/**/*.cpp"),
            *ROOT.glob("toolchain/**/*.hpp"),
            *ROOT.glob("isa/**/*.json"),
            *ROOT.glob("verification/**/*.py"),
            *ROOT.glob("verification/**/*.cpp"),
            ROOT / "sim/emulator.cpp",
        }
    )
    metadata = {
        "architecture": "MICA 2.0",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.platform(),
        "tools": versions,
        "regression_stages_passed": len(stages),
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sources
        },
        "limits": "Local tool-based verification, not an independent lab review, full CPU formal proof, physical board test, routed timing or power measurement.",
    }
    if args.sanitizers_log:
        if "100% tests passed" not in args.sanitizers_log.read_text():
            raise SystemExit("sanitizer log does not contain a passing CTest summary")
        copy(args.sanitizers_log, "logs/sanitizers.log.gz", True)
        metadata["sanitizers"] = {
            "checks": "AddressSanitizer, UndefinedBehaviorSanitizer, 10000-run seeded ELF fuzz campaign",
            "environment": {"ASAN_OPTIONS": "detect_leaks=0"},
            "limitation": "LeakSanitizer cannot inspect processes in this restricted environment; leak detection was disabled for the successful run.",
        }
    if args.sanitizer_constraint_log:
        copy(
            args.sanitizer_constraint_log,
            "logs/sanitizers-lsan-unavailable.log.gz",
            True,
        )
    (out / "environment.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print("Archived MICA 2.0 evidence:", out)


if __name__ == "__main__":
    main()
