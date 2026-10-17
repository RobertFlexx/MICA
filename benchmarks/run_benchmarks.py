#!/usr/bin/env python3
"""Baseline local software metrics; NOT hardware clock/energy benchmark."""

import csv
import os
import re
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
AS = os.getenv("MICA_AS", str(ROOT / "build/mica-as"))
SIM = os.getenv("MICA_RUN", str(ROOT / "build/mica-run"))
PROGRAMS = [
    ("arithmetic32.mica", []),
    ("arithmetic64.mica", ["--xlen", "64"]),
    ("div32.mica", []),
    ("div64.mica", ["--xlen", "64"]),
    ("string32.mica", []),
    ("vector32.mica", ["--simd"]),
    ("atomic32.mica", ["--atomic"]),
]
with tempfile.TemporaryDirectory() as tmp:
    writer = csv.writer(os.sys.stdout)
    writer.writerow(
        ["program", "xlen", "rom_bytes", "emulator_retired_instructions", "notes"]
    )
    for name, flags in PROGRAMS:
        out = Path(tmp) / "program.bin"
        subprocess.run(
            [AS, *flags, "-o", str(out), str(ROOT / "examples" / name)],
            check=True,
            capture_output=True,
        )
        p = subprocess.run(
            [SIM, *flags, str(out)], check=True, text=True, capture_output=True
        )
        match = re.search(r"cycles=(\d+)", p.stderr)
        # The emulator increments once per modeled instruction; it is not a CPU cycle simulator.
        writer.writerow(
            [
                name,
                64 if "--xlen" in flags else 32,
                out.stat().st_size,
                match.group(1) if match else "",
                "1 instruction/step functional model; NOT MHz or energy",
            ]
        )
