#!/usr/bin/env python3
"""Reproducible add64 equivalence, synthesis and RTL transition experiment."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, default=ROOT / "build/alu-research")
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)


def checked(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise RuntimeError(r.stdout + r.stderr)
    return r.stdout + r.stderr


with tempfile.TemporaryDirectory(prefix="mica-alu-") as temp:
    stage = Path(temp)
    for name in ["mica_add64.sv", "tb_add64.sv"]:
        shutil.copyfile(ROOT / "rtl" / name, stage / name)
    checked(["iverilog", "-g2012", "-s", "tb_add64", "-o", "sim", "mica_add64.sv", "tb_add64.sv"], stage)
    (a.output / "simulation.log").write_text(checked(["vvp", "sim"], stage))
    shutil.copyfile(stage / "add64.vcd", a.output / "add64.vcd")
    counts = {}
    for top in ["mica_add64_full", "mica_add64_segmented"]:
        script = f"read_verilog -sv mica_add64.sv; synth -top {top}; abc -lut 6; check; tee -o {top}.json stat -json"
        (a.output / (top + ".log")).write_text(checked(["yosys", "-Q", "-p", script], stage))
        stats = json.loads((stage / (top + ".json")).read_text())
        counts[top] = stats["modules"]["\\" + top]["num_cells_by_type"]
    paths, scopes, previous, transitions = {}, [], {}, {}
    wanted = {"tb_add64.full.sum": 32, "tb_add64.segmented.high_sum": 0,
              "tb_add64.full.b": 32, "tb_add64.segmented.high_b": 0}
    for line in (stage / "add64.vcd").read_text().splitlines():
        words = line.split()
        if line.startswith("$scope"):
            scopes.append(words[2])
        elif line.startswith("$upscope"):
            scopes.pop()
        elif line.startswith("$var"):
            name = ".".join([*scopes, words[4]])
            if name in wanted:
                paths.setdefault(words[3], []).append(name)
                transitions[name] = 0
        elif line.startswith("b") and len(words) == 2 and words[1] in paths:
            bits = words[0][1:]
            if "x" in bits or "z" in bits:
                continue
            raw = int(bits, 2)
            for name in paths[words[1]]:
                value = (raw >> wanted[name]) & 0xffffffff
                if name in previous:
                    transitions[name] += (previous[name] ^ value).bit_count()
                previous[name] = value
    if set(transitions) != set(wanted):
        raise RuntimeError("VCD signal names changed; update the experiment")
    report = {"hypothesis": "isolating the upper adder reduces internal activity for narrow operations",
              "vectors": 10000, "narrow_fraction": 0.9, "seed": "d4a97f03be618c25",
              "method": "RTL stable-value bit transitions, not capacitance-weighted energy or glitch power",
              "tools": {name: checked(cmd, stage).strip() for name, cmd in
                        [("yosys", ["yosys", "-V"]), ("iverilog", ["iverilog", "-V"])]},
              "cells_after_lut6_mapping": counts, "bit_transitions": transitions}
    (a.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"cells": counts, "transitions": transitions}, indent=2))
