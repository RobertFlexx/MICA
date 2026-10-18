#!/usr/bin/env python3
"""Convert bytes to little-endian $readmemh words (8-bit legacy default)."""

import argparse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("input", type=Path)
p.add_argument("output", type=Path)
p.add_argument("--width", type=int, choices=[8, 32, 64], default=8)
p.add_argument("--pad-bytes", type=int, default=0)
a = p.parse_args()
if a.input.stat().st_size > 32 * 1024 * 1024:
    p.error("input exceeds 32MiB")
data = a.input.read_bytes()
if a.pad_bytes:
    if a.pad_bytes < len(data) or a.pad_bytes > 32 * 1024 * 1024:
        p.error("padding must contain the input and fit 32MiB")
    data = data.ljust(a.pad_bytes, b"\0")
n = a.width // 8
data = data.ljust((len(data) + n - 1) // n * n, b"\0")
a.output.write_text("".join(f"{int.from_bytes(data[i:i+n], 'little'):0{n*2}x}\n" for i in range(0, len(data), n)))
print(f"wrote {len(data)} bytes as {a.width}-bit words")
