#!/usr/bin/env python3
"""Existing 1.0 firmware must assemble to the identical bytes.

These are frozen images from the previous MICA 1.0 SDK release. New extension
opcodes must not alter their encodings. The check uses the current assembler.
"""

from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LEDGER = json.loads((ROOT / "isa/compatibility.json").read_text())["vectors"]
IMAGES = [v["name"] for v in LEDGER]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--as", dest="assembler", type=Path, default=ROOT / "build/mica-as"
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        for vector in LEDGER:
            name = vector["name"]
            src = ROOT / "examples" / f"{name}.mica"
            expected = ROOT / "examples/firmware" / f"{name}.bin"
            if not src.is_file() or not expected.is_file():
                raise SystemExit(f"missing frozen vector: {name}")
            flags = []
            if name.endswith("64"):
                flags += ["--xlen", "64"]
            if name.startswith("flow_"):
                flags += ["--flow"]
            if name.startswith("bitops"):
                flags += ["--bitops"]
            if name.startswith("trap"):
                flags += ["--trap"]
            if hashlib.sha256(expected.read_bytes()).hexdigest() != vector["sha256"]:
                raise SystemExit("frozen vector hash changed: " + name)
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
            emulator = os.environ.get("MICA_RUN", str(args.assembler.parent / "mica-run"))
            result = subprocess.run([emulator, *vector["flags"], "--steps", "200000" if vector["kind"] == "halt" else "200", str(expected)], capture_output=True, text=True, timeout=10)
            registers = {k:int(v,16) for k,v in re.findall(r"\bx(\d+)=0x([0-9a-f]+)",result.stderr)}
            if vector["kind"] == "halt" and result.returncode != 0:
                raise SystemExit(name + ": execution failed: " + result.stderr)
            if vector["kind"] != "halt" and (result.returncode != 2 or "step limit exceeded" not in result.stderr):
                raise SystemExit(name + ": expected bounded infinite loop")
            if result.stdout != vector["stdout"] or registers != vector["registers"]:
                raise SystemExit(name + ": behavioral compatibility mismatch")
            print(f"MATCH {name} ({output.stat().st_size} bytes)")
    print(f"PASS {len(IMAGES)} previous 1.0 firmware images unchanged")


if __name__ == "__main__":
    main()
