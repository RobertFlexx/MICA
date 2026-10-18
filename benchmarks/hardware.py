#!/usr/bin/env python3
"""Compare fetch reuse on checked firmware; report RTL cycles and transactions."""

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification/differential"))
from run import compare, checked, FLAGS

p = argparse.ArgumentParser()
p.add_argument("--tools", type=Path, default=ROOT / "build")
p.add_argument("--rtl", type=Path, default=ROOT / "build/rtl")
p.add_argument("--output", type=Path, default=ROOT / "build/hardware-bench")
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
results = []
programs = [
    ("arithmetic32", 32, ROOT / "examples/arithmetic32.mica", 42),
    ("arithmetic64", 64, ROOT / "examples/arithmetic64.mica", 0x0123456889ABCDEE),
    ("memory-copy", 32, ROOT / "examples/flow_copy32.mica", 3),
    ("strings", 32, ROOT / "examples/string32.mica", 4),
    ("division", 32, ROOT / "examples/div32.mica", 858993459),
]
crc = a.output / "crc.mica"
crc.write_text(
    f'li32 x1,data\nli8 x2,9\ncall mica_crc32\nwfi\n.include "{ROOT / "stdlib/checksum32.mica"}"\ndata: .ascii "123456789"\n'
)
programs.append(("crc32", 32, crc, 0xCBF43926))
for name, width, source, expected in programs:
    binary = a.output / (name + ".bin")
    reference = a.output / (name + ".reference.jsonl")
    flags = ["--xlen", str(width), *FLAGS]
    checked([a.tools / "mica-as", *flags, source, "-o", binary])
    checked(
        [
            a.tools / "mica-run",
            *flags,
            "--memory",
            "65536",
            "--retire-trace",
            reference,
            binary,
        ]
    )
    events = [json.loads(x) for x in reference.read_text().splitlines()]
    if events[-1]["regs"][1] != expected:
        raise AssertionError("incorrect benchmark result: " + name)
    if name == "division" and events[-1]["regs"][2] != 0:
        raise AssertionError("incorrect division remainder")
    if name == "memory-copy" and events[-1]["regs"][2:4] != [24, 0]:
        raise AssertionError("incomplete memory copy")
    retired = sum(e["retired"] for e in events)
    for reuse in [0, 1]:
        runs = []
        for seed in [1, 17, 1234, 5678, 99]:
            trace = a.output / f"{name}-{reuse}-{seed}.jsonl"
            result = checked(
                [a.rtl / f"x{width}-reuse{reuse}/Vmica_core_txn", binary, trace, seed]
            )
            compare(reference, trace, name)
            runs.append(json.loads(result.stderr))
        median = statistics.median(r["cycles"] for r in runs)
        results.append(
            {
                "name": name,
                "xlen": width,
                "fetch_reuse": reuse,
                "rom_bytes": binary.stat().st_size,
                "retired": retired,
                "median_cycles": median,
                "ipc": retired / median,
                "fetches_per_retired": runs[0]["fetches"] / retired,
                "runs": runs,
            }
        )
report = {
    "method": "Verilated multicycle core; five fixed seeds; request stalls 25%, response delay 0..8 fetch / 0..10 data; one RAM address space",
    "limits": "No physical clock, routing, energy or independent-ISA baseline measurement",
    "results": results,
}
(a.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
for r in results:
    print(
        r["name"],
        "reuse=" + str(r["fetch_reuse"]),
        "cycles=" + str(r["median_cycles"]),
        "fetch/ret=" + str(round(r["fetches_per_retired"], 3)),
    )
