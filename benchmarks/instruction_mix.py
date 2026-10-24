#!/usr/bin/env python3
"""Count actual retired instructions in compiler-generated conformance programs."""

import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--traces", type=Path, required=True)
parser.add_argument(
    "--output", type=Path, default=ROOT / "build/instruction-mix-v3.json"
)
args = parser.parse_args()
patterns = json.loads((ROOT / "isa/generated/encoding_patterns.json").read_text())
counts, cases = {}, {}
for path in sorted(args.traces.glob("*.jsonl")):
    if ".rtl." in path.name:
        continue
    profile = "MICA-2E" if "MICA-2E" in path.name else "MICA-2C"
    count = Counter()
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if not event["retired"]:
            continue
        raw, length = event["insn"], event["length"]
        code = (raw & 65535) << 16 | (raw >> 16) if length == 4 else raw
        matches = [
            entry
            for entry in patterns
            if entry["length"] == length and code & entry["mask"] == entry["value"]
        ]
        if len(matches) != 1:
            raise ValueError(
                f"{path}: ambiguous/unallocated retired instruction {raw:#x}"
            )
        count[matches[0]["name"]] += 1
    counts.setdefault(profile, Counter()).update(count)
    cases[path.stem] = dict(count.most_common())
if not cases:
    raise SystemExit("no compiler retirement traces found")
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(
    json.dumps(
        {
            "scope": "compiler-generated test firmware; dynamic retired counts, not representative application statistics",
            "profiles": {
                name: dict(count.most_common()) for name, count in counts.items()
            },
            "cases": cases,
        },
        indent=2,
    )
    + "\n"
)
print("PASS instruction frequency analysis:", len(cases), "compiler/profile programs")
