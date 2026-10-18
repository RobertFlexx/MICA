#!/usr/bin/env python3
"""Copy measured reports and deterministic gzip logs after a release regression."""
import argparse
import gzip
import json
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--build", type=Path, default=ROOT / "build/baseline")
p.add_argument("--sanitizers", type=Path, default=ROOT / "build/sanitize")
p.add_argument("--output", type=Path, default=ROOT / "docs/engineering/results")
a = p.parse_args()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=True)
regression = a.build / "validation"
stages = json.loads((regression / "results.json").read_text())
if len(stages) < 20 or any(stage["exit"] for stage in stages):
    raise SystemExit("archive requires the complete successful --all regression")


def copy(source, target, compress=False):
    path = out / target
    path.parent.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    path.write_bytes(gzip.compress(data, mtime=0) if compress else data)


copy(regression / "results.json", "regression.json")
for log in sorted(regression.glob("*.log")):
    copy(log, "regression/" + log.name + ".gz", True)
copy(a.build / "Testing/Temporary/LastTest.log", "software.log.gz", True)
copy(a.sanitizers / "Testing/Temporary/LastTest.log", "sanitizers.log.gz", True)
for directory in ["synthesis", "formal", "alu-research"]:
    for path in sorted((ROOT / "build" / directory).glob("*")):
        if path.suffix == ".json":
            copy(path, directory + "/" + path.name)
        elif path.suffix == ".log":
            copy(path, directory + "/" + path.name + ".gz", True)
for source, name in [("build/hardware-bench/results.json", "fetch-results.json"),
                     ("build/differential/results.json", "differential-results.json"),
                     ("build/emulator-r2.json", "emulator-results.json")]:
    copy(ROOT / source, name)
copy(ROOT / "build/peripherals/commands.log", "peripherals.log.gz", True)
for name in ["crc32", "mica_uart_rx", "mica_sync_fifo", "crc-mmio", "peripherals32", "peripherals64", "arty"]:
    copy(ROOT / "build/peripherals" / (name + ".vcd"), "waveforms/" + name + ".vcd.gz", True)
copy(ROOT / "rtl/watchdog.vcd", "waveforms/watchdog.vcd.gz", True)
copy(ROOT / "build/sram-xilinx.log", "sram-64KiB.log.gz", True)
versions = {}
for command in [["g++", "--version"], ["clang++", "--version"], ["cmake", "--version"], ["yosys", "-V"],
                ["verilator", "--version"], ["ghdl", "--version"], ["iverilog", "-V"], ["sby", "--version"], ["z3", "--version"],
                ["actionlint", "--version"]]:
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    versions[command[0]] = (result.stdout + result.stderr).splitlines()[0]
metadata = {"architecture": "MICA 1.0", "engineering_revision": "r2", "date": "2026-10-17",
            "host": platform.platform(), "tools": versions, "regression_stages_passed": len(stages),
            "limits": "No Vivado, physical FPGA, vendor timing/power or whole-CPU formal result"}
(out / "environment.json").write_text(json.dumps(metadata, indent=2) + "\n")
print("Archived measured evidence: " + str(out))
