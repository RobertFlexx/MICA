#!/usr/bin/env python3
"""Compile a restricted freestanding C subset through Clang's unoptimized IR."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import json

from mica_ir import Module, Unsupported


def main():
    folder = Path(__file__).resolve().parents[1]
    metadata = folder / "release.json"
    if not metadata.exists():
        metadata = folder / "share/mica/release.json"
    release = json.loads(metadata.read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        action="version",
        version=f"mica-cc {release['sdk_version']} {release['stage']} r{release['revision']} (restricted Clang IR lowering)",
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", type=Path, required=True)
    parser.add_argument("-S", action="store_true", help="emit MICA assembly")
    parser.add_argument("--profile", choices=["MICA-2C", "MICA-2E"], default="MICA-2E")
    parser.add_argument("--clang", default="clang")
    installed = Path(__file__).resolve().parent / "mica-as"
    parser.add_argument(
        "--assembler",
        default=(
            str(installed)
            if installed.is_file()
            else shutil.which("mica-as")
            or str(Path(__file__).resolve().parents[1] / "build/mica-as")
        ),
    )
    args = parser.parse_args()
    if args.source.stat().st_size > 1024 * 1024:
        raise Unsupported("source exceeds 1 MiB")
    with tempfile.TemporaryDirectory(prefix="mica-cc-") as temp:
        ir, assembly, obj = [
            Path(temp) / name for name in ("input.ll", "output.mica", "output.o")
        ]
        result = subprocess.run(
            [
                args.clang,
                "--target=riscv32-unknown-elf",
                "-ffreestanding",
                "-fno-builtin",
                "-fno-discard-value-names",
                "-O0",
                "-S",
                "-emit-llvm",
                str(args.source.resolve()),
                "-o",
                str(ir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode:
            raise Unsupported(result.stderr.strip())
        code = Module(
            ir.read_text(),
            multiply=args.profile == "MICA-2E",
            expanded=args.profile == "MICA-2E",
        ).assembly()
        assembly.write_text(code)
        if args.S:
            args.o.write_text(code)
        else:
            result = subprocess.run(
                [
                    args.assembler,
                    "--profile",
                    args.profile,
                    "-c",
                    str(assembly),
                    "-o",
                    str(obj),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise Unsupported(result.stderr.strip())
            args.o.write_bytes(obj.read_bytes())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("mica-cc: " + str(error), file=sys.stderr)
        sys.exit(1)
