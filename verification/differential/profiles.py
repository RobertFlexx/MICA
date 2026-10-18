#!/usr/bin/env python3
"""Check actual disabled-extension RTL configurations, including fatal faults."""
import argparse
from pathlib import Path
import subprocess
from run import compare, checked

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument("--tools", type=Path, default=ROOT / "build")
p.add_argument("--rtl", type=Path, default=ROOT / "build/rtl")
p.add_argument("--output", type=Path, default=ROOT / "build/profile-tests")
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
cases = [
    ("MICA-C", "base", "li8 x1,21\nadd x1,x1\nwfi\n", 0),
    ("MICA-C", "features", "csrr x1,features\ncsrr x2,arch\nwfi\n", 0),
    ("MICA-E", "features", "csrr x1,features\ncsrr x2,arch\nwfi\n", 0),
    ("MICA-E", "multiply", "li8 x1,6\nli8 x2,7\nmul x1,x2\nwfi\n", 0),
    ("MICA-C", "disabled-multiply", "li8 x1,55\nmul x1,x1\nwfi\n", 2),
    ("MICA-C", "disabled-flow", "li32 x1,32768\nldpi.b x2,[x1]\nwfi\n", 2),
    ("MICA-C", "disabled-bits", "popcnt3 x1,x2\nwfi\n", 2),
    ("MICA-C", "disabled-xreg", "li16 x8,42\nwfi\n", 2),
    ("MICA-C", "disabled-csr", "csrr x1,status\nwfi\n", 2),
    ("MICA-C", "invalid-shift", ".half 0x5920\nwfi\n", 2),
    ("MICA-E", "disabled-xreg", "li16 x8,42\nwfi\n", 2),
    ("MICA-C", "reserved-alias", ".half 0x1000\nwfi\n", 2),
]
for profile, name, source, expected in cases:
    path = a.output / (profile + "-" + name + ".mica")
    path.write_text(source)
    binary, reference, rtltrace = [path.with_suffix(ext) for ext in [".bin", ".ref.jsonl", ".rtl.jsonl"]]
    checked([a.tools / "mica-as", "--xreg", "--mul", "--flow", "--bitops", path, "-o", binary])
    commands = [[a.tools / "mica-run", "--profile", profile, "--memory", "65536", "--retire-trace", reference, binary],
                [a.rtl / (profile + "-reuse1/Vmica_core_txn"), binary, rtltrace, 17]]
    for command in commands:
        result = subprocess.run([str(x) for x in command], capture_output=True, text=True, timeout=10)
        if result.returncode != expected:
            raise AssertionError(f"{name}: exit {result.returncode} != {expected}: {result.stderr}")
    compare(reference, rtltrace, profile + "/" + name)
print(f"PASS {len(cases)} configured profile programs, including disabled instruction faults")
