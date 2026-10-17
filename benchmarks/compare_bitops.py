#!/usr/bin/env python3
"""End-to-end instruction-count/code-size comparison. No cycle/power claim."""

from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(asm, emulator, source, bitops):
    with tempfile.TemporaryDirectory() as temp:
        binfile = Path(temp) / "program.bin"
        flags = ["--bitops"] if bitops else []
        subprocess.run(
            [str(asm), *flags, str(source), "-o", str(binfile)],
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            [str(emulator), *flags, str(binfile)],
            check=True,
            capture_output=True,
            text=True,
        )
        match = re.search(r"\bx1=0x([0-9a-f]+)", result.stderr)
        retired = re.search(r"\bretired=(\d+)", result.stderr)
        if not (match and retired):
            raise RuntimeError("emulator did not return required counters")
        data = binfile.read_bytes()
        return {
            "output": int(match.group(1), 16),
            "retired_instructions": int(retired.group(1)),
            "image_bytes": len(data),
            "image_sha256": hashlib.sha256(data).hexdigest(),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--as", dest="assembler", type=Path, default=ROOT / "build/mica-as"
    )
    parser.add_argument(
        "--run", dest="emulator", type=Path, default=ROOT / "build/mica-run"
    )
    args = parser.parse_args()
    baseline = run(
        args.assembler, args.emulator, ROOT / "benchmarks/popcnt_soft.mica", False
    )
    bitops = run(
        args.assembler, args.emulator, ROOT / "benchmarks/popcnt_bitops.mica", True
    )
    if baseline["output"] != 16 or bitops["output"] != 16:
        raise RuntimeError("result mismatch; benchmark invalid")
    print(
        json.dumps(
            {
                "benchmark": "popcount_of_f0f0f0f0",
                "platform": "MICA32 functional emulator",
                "includes_call_setup": True,
                "baseline": baseline,
                "bitops": bitops,
                "note": "retired instructions and image bytes only; no time, power, or Fmax measurements",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
