#!/usr/bin/env python3
"""Build valid ELF and corrupt-header seed inputs using the current assembler."""

import argparse
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument("--assembler", required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="mica-seed-") as temp:
    source = Path(temp) / "seed.mica"
    source.write_text(
        ".global _start\n.extern routine\n_start: li32 x1,datum\ncall routine\nwfi\ndatum: .word _start\n"
    )
    subprocess.run(
        [a.assembler, "-c", str(source), "-o", str(a.output / "valid.o")], check=True
    )
(a.output / "truncated").write_bytes(b"\x7fELF\x02\x01\x01")
