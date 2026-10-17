#!/usr/bin/env python3
"""Measure exact MICA loop body sizes, not performance or power."""

import argparse
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument("--assembler", default="build/mica-as")
a = p.parse_args()
base = """.arch mica32
loop: ldbu x4,[x2]
stb x4,[x1]
addi x1,1
addi x2,1
addi x3,-1
bnz x3,loop
"""
flow = """.arch mica32
loop: ldpi.b x4,[x2]
stpi.b x4,[x1]
dbnz x3,loop
"""
with tempfile.TemporaryDirectory() as tmp:
    for name, code, flags in [("base", base, []), ("flow", flow, ["--flow"])]:
        path = Path(tmp) / f"{name}.mica"
        output = Path(tmp) / f"{name}.bin"
        path.write_text(code)
        subprocess.run(
            [a.assembler, *flags, str(path), "-o", str(output)],
            check=True,
            capture_output=True,
        )
        print(f"{name}: {len(output.read_bytes())} bytes")
