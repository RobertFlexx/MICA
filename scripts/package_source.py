#!/usr/bin/env python3
"""Deterministic source archive from nonignored repository files, with checksums."""

import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile

from source_files import source_files

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument(
    "--output", type=Path, default=ROOT / "build/releases/mica-sdk-2.0-source.tar.gz"
)
p.add_argument("--update-checksums", action="store_true")
a = p.parse_args()
files = []
for name in source_files(ROOT):
    path = ROOT / name
    if path.is_symlink() or not path.is_file():
        raise SystemExit("source archive requires regular files: " + name)
    files.append(name)
if "SHA256SUMS" not in files:
    files.append("SHA256SUMS")
    files.sort()
checksums = "".join(
    hashlib.sha256((ROOT / name).read_bytes()).hexdigest() + "  " + name + "\n"
    for name in files
    if name != "SHA256SUMS"
)
if a.update_checksums:
    (ROOT / "SHA256SUMS").write_text(checksums)
elif (ROOT / "SHA256SUMS").read_text() != checksums:
    raise SystemExit("stale source checksums; review files then use --update-checksums")
a.output.parent.mkdir(parents=True, exist_ok=True)
with a.output.open("wb") as raw, gzip.GzipFile(
    filename="", fileobj=raw, mode="wb", mtime=0
) as zipped:
    with tarfile.open(fileobj=zipped, mode="w|") as archive:
        for name in files:
            path = ROOT / name
            data = path.read_bytes()
            info = tarfile.TarInfo("mica-sdk-2.0/" + name)
            info.size = len(data)
            info.mode = path.stat().st_mode & 0o777
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
print(a.output, hashlib.sha256(a.output.read_bytes()).hexdigest())
