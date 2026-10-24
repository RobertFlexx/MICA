#!/usr/bin/env python3
"""Check all scalar product forms against Python integer arithmetic and RTL."""

import argparse
import json
from pathlib import Path
import random

from run import checked, compare

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tools", type=Path, required=True)
parser.add_argument("--rtl", type=Path, default=ROOT / "build/rtl")
parser.add_argument("--output", type=Path, default=ROOT / "build/multiply-tests")
args = parser.parse_args()
args.tools = args.tools.resolve()
args.output.mkdir(parents=True, exist_ok=True)
patterns = json.loads((ROOT / "isa/generated/encoding_patterns.json").read_text())
products = [entry for entry in patterns if entry["name"] in ("mul", "mul3", "mulw3")]
rows = []
for width, profile in ((32, "MICA-2E"), (64, "MICA-2L")):
    mask = (1 << width) - 1
    boundary = [0, 1, 2, mask, mask - 1, 1 << (width - 1), (1 << (width - 1)) - 1]
    rng = random.Random(0x30A0 + width)
    pairs = [(a, b) for a in boundary for b in boundary]
    pairs += [(rng.getrandbits(width), rng.getrandbits(width)) for _ in range(64)]
    expected, source = [], [f".arch mica{width}v2"]
    for a, b in pairs:
        product = (a * b) & mask
        source += [f"li{width} x1,{a}", f"li{width} x2,{b}", "mul x1,x2"]
        expected.append((1, product))
        source += [f"li{width} x9,{a}", f"li{width} x10,{b}", "mul3 x8,x9,x10"]
        expected.append((8, product))
        if width == 64:
            word = (a * b) & 0xFFFFFFFF
            signed = (word - (1 << 32) if word & 0x80000000 else word) & mask
            source += ["mulw3 x15,x9,x10"]
            expected.append((15, signed))
        source += ["mul3 x9,x9,x10", "mul x0,x2"]
        expected += [(9, product), (0, 0)]
    source += ["stop"]
    stem = args.output / profile
    assembly, binary, reference, actual = [
        stem.with_suffix(s) for s in (".mica", ".bin", ".ref.jsonl", ".rtl.jsonl")
    ]
    assembly.write_text("\n".join(source) + "\n")
    checked([args.tools / "mica-as", "--profile", profile, assembly, "-o", binary])
    checked(
        [
            args.tools / "mica-run",
            "--profile",
            profile,
            "--memory",
            65536,
            "--steps",
            20000,
            "--retire-trace",
            reference,
            binary,
        ]
    )
    observed = []
    for event in map(json.loads, reference.read_text().splitlines()):
        raw = event["insn"]
        code = ((raw & 65535) << 16) | (raw >> 16) if event["length"] == 4 else raw
        if event["retired"] and any(
            event["length"] == p["length"] and code & p["mask"] == p["value"]
            for p in products
        ):
            if event["regs"][0] != 0:
                raise AssertionError("multiply corrupted x0")
            observed.append(event)
    if len(observed) != len(expected):
        raise AssertionError("missing or unexpected multiply retirement")
    for index, (event, (dest, value)) in enumerate(zip(observed, expected)):
        if event["regs"][dest] != value:
            raise AssertionError(
                f"{profile} product {index}: expected {value:#x}, observed {event['regs'][dest]:#x}"
            )
    driver = args.rtl.resolve() / f"{profile}-reuse1/Vmica_core_txn"
    runs = []
    for seed in (1, 17, 1234):
        result = checked([driver, binary, actual, seed])
        compare(reference, actual, f"{profile}/multiply/{seed}")
        runs.append(json.loads(result.stderr))
    rows.append(
        {
            "profile": profile,
            "operand_pairs": len(pairs),
            "independent_products": len(expected),
            "oracle": "Python unbounded integer multiply, explicit XLEN truncation and W32 sign extension",
            "rtl_runs": runs,
        }
    )
    print(
        f"PASS {profile}: {len(expected)} products and three RTL stall seeds",
        flush=True,
    )
(args.output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
