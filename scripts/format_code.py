#!/usr/bin/env python3
"""Format SDK sources with repository settings; --check verifies without edits."""

import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--cmake-format", default="cmake-format")
    args = parser.parse_args()
    names = subprocess.check_output(
        [
            "rg",
            "--files",
            "--hidden",
            "-g",
            "!build*/**",
            "-g",
            "!.git/**",
            "-g",
            "!.agents/**",
            "-g",
            "!.aws/**",
            "-g",
            "!.codex/**",
        ],
        cwd=ROOT,
        text=True,
    ).splitlines()
    stale = []
    count = 0
    for name in sorted(names):
        path = ROOT / name
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
        elif (
            suffix
            not in [
                ".json",
                ".mica",
                ".vhd",
                ".tcl",
                ".xdc",
                ".sh",
                ".yml",
                ".yaml",
                ".toml",
                ".extras",
            ]
            and path.name != "Makefile"
        ):
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
        elif suffix == ".json":
            formatted = (
                json.dumps(json.loads(original), indent=2, ensure_ascii=False) + "\n"
            )
        else:
            # Whitespace-only cleanup for assembly, VHDL, Tcl and build metadata.
            # Preserve Make recipe tabs, quoted strings and existing nesting.
            formatted = (
                "\n".join(line.rstrip() for line in original.splitlines()).rstrip()
                + "\n"
            )
        count += 1
        if formatted != original:
            if args.check:
                stale.append(name)
            else:
                path.write_text(formatted)
    if stale:
        raise SystemExit("Formatting required:\n" + "\n".join(stale))
    print(f"PASS {count} source/build files {'checked' if args.check else 'formatted'}")


if __name__ == "__main__":
    main()
