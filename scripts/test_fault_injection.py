#!/usr/bin/env python3
"""Measure a bounded, targeted register/memory/control/fetch fault campaign."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tools", type=Path, default=ROOT / "build")
parser.add_argument("--output", type=Path, default=ROOT / "build/fault-injection")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)


def run(command):
    result = subprocess.run(
        [str(x) for x in command], cwd=out, capture_output=True, text=True, timeout=30
    )
    with (out / "commands.log").open("a") as log:
        log.write(
            repr([str(x) for x in command]) + "\n" + result.stdout + result.stderr
        )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


(out / "commands.log").write_text("")
run(
    [
        args.tools.resolve() / "mica-as",
        "--mica2",
        "--trap",
        ROOT / "firmware/examples/fault_probe32.mica",
        "-o",
        out / "probe.bin",
    ]
)
run(
    [
        sys.executable,
        ROOT / "toolchain/bin2mem8.py",
        out / "probe.bin",
        out / "fault-probe.mem32",
        "--width",
        32,
        "--pad-bytes",
        65536,
    ]
)
sources = [
    ROOT / ("rtl/" + name)
    for name in (
        "mica_core_txn.sv",
        "mica_soc.sv",
        "mica_uart_tx.sv",
        "mica_crc_mmio.sv",
        "verilog/mica_sram_txn.v",
        "verilog/mica_uart_tx_portable.v",
        "tb_fault_injection.sv",
    )
]
results = []
for parity in (0, 1):
    binary = out / f"fault-sim{parity}"
    run(
        [
            "iverilog",
            "-g2012",
            "-I" + str(ROOT / "isa/generated"),
            "-s",
            "tb_fault_injection",
            f"-Ptb_fault_injection.REG_PARITY={parity}",
            "-o",
            binary,
            *sources,
        ]
    )
    for kind in range(5):
        for bit in range(32) if kind < 2 else [0]:
            run(["vvp", binary, f"+KIND={kind}", f"+BIT={bit}"])
            outcome = (
                "fail-stop"
                if kind == 2 or (kind == 0 and parity)
                else "precise trap" if kind in (3, 4) else "undetected corruption"
            )
            results.append(
                {
                    "reg_parity": parity,
                    "target": (
                        "register x1",
                        "data SRAM",
                        "FSM",
                        "PC alignment",
                        "instruction response",
                    )[kind],
                    "bit": bit if kind < 2 else None,
                    "outcome": outcome,
                }
            )
report = {
    "method": "One injection per reset at a WFI boundary. Sweep all 32 x1 bits and all 32 bits of one data word; selected invalid FSM, odd PC and instruction response errors.",
    "limits": "Targeted simulation, not exhaustive fault coverage. No register correction, SRAM protection, CSR parity, lockstep, radiation or safety qualification. Even-bit register errors and errors outside the check boundary can escape detection.",
    "results": results,
}
(out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
print(
    f"PASS {len(results)} targeted fault injections; unprotected corruption remains explicitly recorded"
)
