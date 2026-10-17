#!/usr/bin/env python3
"""Existing 1.0 firmware must assemble to the identical bytes.

These are frozen images from the previous MICA 1.0 SDK release. New extension
opcodes must not alter their encodings. The check uses the current assembler.
"""

from pathlib import Path
import argparse
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
IMAGES = [
    "arena32",
    "arena64",
    "arithmetic32",
    "arithmetic64",
    "console64",
    "flow_copy32",
    "flow_copy64",
    "fpga_blink32",
    "fpga_uart32",
    "hello32",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--as", dest="assembler", type=Path, default=ROOT / "build/mica-as"
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        for name in IMAGES:
            src = ROOT / "examples" / f"{name}.mica"
            expected = ROOT / "examples/firmware" / f"{name}.bin"
            if not src.is_file() or not expected.is_file():
                raise SystemExit(f"missing frozen vector: {name}")
            flags = []
            if name.endswith("64"):
                flags += ["--xlen", "64"]
            if name.startswith("flow_"):
                flags += ["--flow"]
            output = Path(temp) / f"{name}.bin"
            proc = subprocess.run(
                [str(args.assembler), *flags, "-o", str(output), str(src)],
                capture_output=True,
                text=True,
            )
            if proc.returncode:
                raise SystemExit(f"{name}: assembly failed: {proc.stderr}")
            if output.read_bytes() != expected.read_bytes():
                raise SystemExit(f"{name}: byte mismatch")
            print(f"MATCH {name} ({output.stat().st_size} bytes)")
    print(f"PASS {len(IMAGES)} previous 1.0 firmware images unchanged")


if __name__ == "__main__":
    main()
