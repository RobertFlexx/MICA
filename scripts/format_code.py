#!/usr/bin/env python3
"""Format SDK sources with repository settings; --check verifies without edits."""

import argparse
import json
from pathlib import Path
import subprocess

from source_files import source_files

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--cmake-format", default="cmake-format")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="format only this repository-relative source file (repeatable)",
    )
    args = parser.parse_args()
    names = source_files(ROOT)
    if args.path:
        selected = set(names)
        for name in args.path:
            if name not in selected:
                raise SystemExit("not a tracked or nonignored source file: " + name)
        names = args.path
    stale = []
    pending = []
    count = 0
    for name in sorted(set(names)):
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise SystemExit("source formatter requires regular files: " + name)
        # Machine-generated tables and Graphviz drawings retain generator output.
        if "generated" in path.relative_to(ROOT).parts:
            continue
        suffix = path.suffix
        command = None
        if suffix in [".cpp", ".hpp", ".h", ".c", ".cc", ".inc", ".sv", ".v", ".svh"]:
            command = ["clang-format", "--style=file", str(path)]
        elif suffix == ".py":
            command = [
                "black",
                "--quiet",
                "--config",
                str(ROOT / "pyproject.toml"),
                "-",
            ]
        elif path.name == "CMakeLists.txt" or suffix == ".cmake":
            command = [
                args.cmake_format,
                "-c",
                str(ROOT / ".cmake-format.yaml"),
                "--",
                str(path),
            ]
        elif suffix != ".json":
            # Do not blindly trim .sh here-docs, assembly strings, or YAML
            # block scalars. Those spaces can be part of the program/data.
            continue
        original = path.read_text()
        if command:
            result = subprocess.run(
                command,
                input=original if suffix == ".py" else None,
                capture_output=True,
                text=True,
                cwd=ROOT,
                check=True,
            )
            formatted = result.stdout
            if original.strip() and not formatted.strip():
                raise SystemExit("formatter returned empty output for " + name)
        else:
            formatted = (
                json.dumps(json.loads(original), indent=2, ensure_ascii=False) + "\n"
            )
        count += 1
        if formatted != original:
            if args.check:
                stale.append(name)
            else:
                pending.append((path, formatted))
    if stale:
        raise SystemExit("Formatting required:\n" + "\n".join(stale))
    # Do not modify half the repository when a formatter is absent or fails.
    # All subprocesses and parsing must succeed before any source is written.
    for path, formatted in pending:
        path.write_text(formatted)
    print(f"PASS {count} source/build files {'checked' if args.check else 'formatted'}")


if __name__ == "__main__":
    main()
