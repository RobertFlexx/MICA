#!/usr/bin/env python3
"""Run narrow proofs in space-free temporary paths (required by SBY)."""

import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, default=ROOT / "build/formal")
p.add_argument("--timeout", type=int, default=300, help="seconds per proof")
a = p.parse_args()
if a.timeout < 1:
    p.error("--timeout must be positive")
a.output.mkdir(parents=True, exist_ok=True)
for name in ["add64", "sram", "fifo", "spi"]:
    with tempfile.TemporaryDirectory(prefix="mica-proof-") as temp:
        try:
            result = subprocess.run(
                ["sby", "-f", "-d", str(Path(temp) / name), name + ".sby"],
                cwd=ROOT / "verification/formal",
                capture_output=True,
                text=True,
                timeout=a.timeout,
            )
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or b"") + (error.stderr or b"")
            (a.output / (name + ".log")).write_text(
                output.decode(errors="replace") + "\nTIMEOUT\n"
            )
            raise SystemExit(
                f"FAIL {name}: exceeded {a.timeout} seconds; log retained"
            ) from error
        (a.output / (name + ".log")).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise SystemExit(result.stdout + result.stderr)
        print("PASS", name, flush=True)
