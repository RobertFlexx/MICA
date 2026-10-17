#!/usr/bin/env python3
"""Convert a MICA flat binary to $readmemh one-byte-per-line format."""
import sys
from pathlib import Path
if len(sys.argv) != 3:
    sys.exit('usage: python3 toolchain/bin2mem8.py PROGRAM.bin program.mem8')
data = Path(sys.argv[1]).read_bytes()
Path(sys.argv[2]).write_text(''.join(f'{byte:02x}\n' for byte in data))
print(f'wrote {len(data)} bytes')
