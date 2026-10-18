#!/usr/bin/env python3
"""Build a Verilator retirement driver; no downloaded build dependencies."""
import argparse
from pathlib import Path
import subprocess
import shutil
import os
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--xlen", type=int, choices=[32, 64], default=32)
p.add_argument("--profile", choices=["MICA-C", "MICA-E", "MICA-64"])
p.add_argument("--reuse", type=int, choices=[0, 1], default=1)
p.add_argument("--build-dir", type=Path, default=ROOT / "build/rtl")
p.add_argument("--verilator", default="verilator")
a = p.parse_args()
profile = json.loads((ROOT / "isa/profiles/profiles.json").read_text())["profiles"].get(a.profile) if a.profile else None
if profile:
    a.xlen = profile["xlen"]
ext = profile["extensions"] if profile else ["X","M","F","B","T"]
out = a.build_dir.resolve() / ((a.profile if a.profile else f"x{a.xlen}") + f"-reuse{a.reuse}")
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="mica-verilator-") as temp:
    stage = Path(temp)
    for source in [ROOT / "rtl/mica_core_txn.sv", ROOT / "isa/generated/mica_isa.svh",
                   ROOT / "verification/differential/rtl_driver.cpp"]:
        shutil.copyfile(source, stage / source.name)
    cmd = [a.verilator, "--cc", "--exe", "--build", "--assert", "-DMICA_ASSERTIONS", "-j", "4", "--top-module", "mica_core_txn",
           "-Wall", "-Wno-UNUSEDPARAM", "-I.", "--Mdir", "obj", "-CFLAGS", f"-DMICA_XLEN={a.xlen}",
           f"-GXLEN={a.xlen}", f"-GXREG={int('X' in ext)}", f"-GMUL={int('M' in ext)}", f"-GFLOW={int('F' in ext)}", f"-GBITOPS={int('B' in ext)}", f"-GTRAP={int('T' in ext)}",
           f"-GFETCH_REUSE={a.reuse}", "mica_core_txn.sv", "rtl_driver.cpp"]
    environment = os.environ.copy()
    environment["MAKEFLAGS"] = "--jobserver-style=pipe"
    result = subprocess.run(cmd, cwd=stage, env=environment, capture_output=True, text=True)
    (out / "build.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    shutil.copy2(stage / "obj/Vmica_core_txn", out / "Vmica_core_txn")
print(out / "Vmica_core_txn")
