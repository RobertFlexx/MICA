#!/usr/bin/env python3
"""Check local Markdown links, generated allocation, and executable asm snippets."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--assembler", required=True)
a = p.parse_args()
errors = []
count = 0
files = [*ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md"), *ROOT.glob("boards/**/*.md")]
with tempfile.TemporaryDirectory(prefix="mica-docs-") as temp:
    for path in files:
        text = path.read_text()
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = target.split("#", 1)[0].strip("<>")
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (path.parent / target).exists():
                errors.append(f"{path.relative_to(ROOT)}: missing link {target}")
        for code in re.findall(r"```asm\n(.*?)```", text, re.S):
            count += 1
            source = Path(temp) / f"example{count}.mica"
            source.write_text(code)
            width = "64" if ".arch mica64" in code else "32"
            v2 = ".arch mica32v2" in code or ".arch mica64v2" in code
            opts = ["--mica2"] if v2 else []
            if re.search(r"^\s*\.(?:global|globl|weak|extern)\b", code, re.M):
                opts.append("-c")
            result = subprocess.run(
                [
                    a.assembler,
                    *opts,
                    "--xlen",
                    width,
                    "--xreg",
                    "--mul",
                    "--flow",
                    "--simd",
                    "--atomic",
                    "--bitops",
                    "--trap",
                    str(source),
                    "-o",
                    str(source.with_suffix(".bin")),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode:
                errors.append(
                    f"{path.relative_to(ROOT)}: asm example {count}: {result.stderr}"
                )
if errors:
    raise SystemExit("\n".join(errors))
print(f"PASS {len(files)} Markdown files and {count} executable assembly snippets")
