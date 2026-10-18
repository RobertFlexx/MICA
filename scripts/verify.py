#!/usr/bin/env python3
"""One-command build/regression with raw logs and a machine-readable summary."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--build-dir", type=Path, default=ROOT / "build/verify")
p.add_argument(
    "--all",
    action="store_true",
    help="require and run HDL, formal, synthesis and research tools",
)
a = p.parse_args()
out = a.build_dir.resolve()
logs = out / "validation"
logs.mkdir(parents=True, exist_ok=True)
if a.all:
    missing = [
        tool
        for tool in [
            "iverilog",
            "vvp",
            "verilator",
            "ghdl",
            "yosys",
            "sby",
            "z3",
            "dot",
            "make",
        ]
        if not shutil.which(tool)
    ]
    if missing:
        raise SystemExit("Missing required --all tools: " + ", ".join(missing))
results = []


def run(name, command):
    started = time.monotonic()
    result = subprocess.run(
        [str(x) for x in command], cwd=ROOT, capture_output=True, text=True
    )
    (logs / (name + ".log")).write_text(result.stdout + result.stderr)
    results.append(
        {
            "name": name,
            "command": [str(x) for x in command],
            "exit": result.returncode,
            "seconds": round(time.monotonic() - started, 3),
        }
    )
    (logs / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(("PASS " if result.returncode == 0 else "FAIL ") + name, flush=True)
    if result.returncode:
        raise SystemExit(result.stdout[-4000:] + result.stderr[-4000:])


configure = ["cmake", "-S", ROOT, "-B", out, "-DCMAKE_BUILD_TYPE=Release"]
if not (out / "CMakeCache.txt").exists() and shutil.which("ninja"):
    configure += ["-G", "Ninja"]
run("configure", configure)
run("build", ["cmake", "--build", out, "--parallel", "4"])
run("software", ["ctest", "--test-dir", out, "--output-on-failure", "--no-tests=error"])
if a.all:
    run(
        "hdl",
        [
            "make",
            "-C",
            "rtl",
            "ASM=" + str(out / "mica-as"),
            "sim32",
            "sim64",
            "sim-mica2-32",
            "sim-mica2-64",
            "sim-mica2-timer32",
            "sim-mica2-timer64",
            "sim-flow32",
            "sim-flow64",
            "sim-bits32",
            "sim-bits64",
            "sim-trap",
            "sim-trap-irq",
            "sim-sram",
            "sim-sram-txn",
            "sim-watchdog",
            "sim-watchdog-soc",
            "sim-firmware",
            "sim-scheduler",
            "sim-add64",
            "sim-peripherals",
        ],
    )
    run(
        "lint",
        [
            "verilator",
            "--lint-only",
            "-Wall",
            "-Wno-UNUSEDPARAM",
            "-Wno-PINCONNECTEMPTY",
            "-Iisa/generated",
            "--top-module",
            "mica_arty_a7",
            "rtl/mica_core_txn.sv",
            "rtl/mica_soc.sv",
            "rtl/mica_uart_tx.sv",
            "rtl/mica_crc_mmio.sv",
            "rtl/verilog/mica_sync_fifo.v",
            "rtl/verilog/mica_uart_rx.v",
            "rtl/verilog/mica_sram_txn.v",
            "boards/arty_a7/mica_arty_a7.sv",
        ],
    )
    for width in [32, 64]:
        for reuse in [0, 1]:
            run(
                f"driver-{width}-{reuse}",
                [
                    sys.executable,
                    "scripts/build_rtl_sim.py",
                    "--xlen",
                    width,
                    "--reuse",
                    reuse,
                ],
            )
    for profile in ["MICA-C", "MICA-E"]:
        run(profile, [sys.executable, "scripts/build_rtl_sim.py", "--profile", profile])
    for profile in ["MICA-2C", "MICA-2E", "MICA-2L"]:
        run(profile, [sys.executable, "scripts/build_rtl_sim.py", "--profile", profile])
    run(
        "differential",
        [sys.executable, "verification/differential/run.py", "--tools", out],
    )
    run(
        "differential-mica2",
        [sys.executable, "verification/differential/mica2.py", "--tools", out],
    )
    run(
        "profiles",
        [sys.executable, "verification/differential/profiles.py", "--tools", out],
    )
    run("formal", [sys.executable, "scripts/run_formal.py"])
    run("synthesis", [sys.executable, "scripts/synthesize.py", "--tools", out])
    run("diagrams", [sys.executable, "scripts/generate_schematics.py", "--check"])
    run("soc-diagram", [sys.executable, "scripts/generate_soc_schematic.py", "--check"])
    run(
        "mica2-diagrams",
        [sys.executable, "scripts/generate_mica2_diagrams.py", "--check"],
    )
    run(
        "overview-diagrams",
        [sys.executable, "scripts/generate_overview_schematics.py", "--check"],
    )
    if shutil.which("llvm-mc") and shutil.which("llvm-objcopy"):
        run(
            "riscv-density",
            [
                sys.executable,
                "benchmarks/riscv_density.py",
                "--assembler",
                out / "mica-as",
                "--emulator",
                out / "mica-run",
            ],
        )
    run("fetch-benchmark", [sys.executable, "benchmarks/hardware.py", "--tools", out])
    run("alu-benchmark", [sys.executable, "benchmarks/alu_activity.py"])
if shutil.which("actionlint"):
    run("workflow", ["actionlint", ".github/workflows/ci.yml"])
print("Evidence: " + str(logs))
