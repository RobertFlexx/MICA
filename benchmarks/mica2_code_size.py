#!/usr/bin/env python3
"""Compare identical short stack/counter workloads; report only observed bytes."""

import argparse
from pathlib import Path
import json
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument("--assembler", type=Path, required=True)
p.add_argument("--emulator", type=Path, required=True)
p.add_argument("--json", type=Path)
a = p.parse_args()

base = """li8 x1,23
{store} x1,[sp+{slot}]
li8 x1,0
{load} x1,[sp+{slot}]
li8 x2,5
again:
  addi x1,1
  {branch} x2,again
{terminal}
"""
rows = []
with tempfile.TemporaryDirectory() as t:
    directory = Path(t)
    for width in (32, 64):
        for rev in (1, 2):
            image = directory / f"mica{rev}-{width}.bin"
            src = directory / f"mica{rev}-{width}.mica"
            use64 = width == 64
            src.write_text(
                f'.arch mica{width}{"v2" if rev==2 else ""}\n'
                + base.format(
                    store="stsp" if rev == 2 else "stq" if use64 else "stw",
                    load="ldsp" if rev == 2 else "ldq" if use64 else "ldw",
                    slot=8 if use64 else 0,
                    branch="dbnz.s" if rev == 2 else "dbnz",
                    terminal="stop" if rev == 2 else "wfi",
                )
            )
            flags = ["--mica2"] if rev == 2 else ["--flow"]
            build = subprocess.run(
                [
                    str(a.assembler),
                    "--xlen",
                    str(width),
                    *flags,
                    str(src),
                    "-o",
                    str(image),
                ],
                capture_output=True,
                text=True,
            )
            if build.returncode:
                raise SystemExit(build.stderr)
            run = subprocess.run(
                [str(a.emulator), "--xlen", str(width), *flags, str(image)],
                capture_output=True,
                text=True,
            )
            if run.returncode or "x1=0x1c" not in run.stderr:
                raise SystemExit(run.stderr)
            rows.append(
                {
                    "mode": f"MICA-{width}",
                    "revision": rev,
                    "program_bytes": image.stat().st_size,
                    "expected_result": 28,
                }
            )
for width in (32, 64):
    old, new = [row["program_bytes"] for row in rows if row["mode"] == f"MICA-{width}"]
    print(
        f"MICA-{width}: {old} -> {new} bytes, {(old-new)/old*100:.1f}% smaller (this test only)"
    )
if a.json:
    a.json.parent.mkdir(parents=True, exist_ok=True)
    a.json.write_text(
        json.dumps(
            {
                "method": "same handwritten stack/counter program, v1 vs v2, independently reassembled and executed",
                "measurements": rows,
            },
            indent=2,
        )
        + "\n"
    )
