#!/usr/bin/env python3
"""Assemble complete zero-safe copy routines for MICA, RISC-V and Thumb."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification/differential"))
from run import compare

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tools", type=Path, default=ROOT / "build")
parser.add_argument("--llvm-mc", default="llvm-mc")
parser.add_argument("--llvm-objcopy", default="llvm-objcopy")
parser.add_argument("--output", type=Path, default=ROOT / "build/control-density")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
tools = args.tools.resolve()
(out / "commands.log").write_text("")


def run(command):
    result = subprocess.run(
        list(map(str, command)), capture_output=True, text=True, timeout=30
    )
    with (out / "commands.log").open("a") as log:
        log.write(repr(list(map(str, command))) + "\n" + result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result


mica = "copy_bytes: bz x3,done\nloop: ldpi.b x4,[x2]\nstpi.b x4,[x1]\ndbnz.s x3,loop\ndone: ret\n"
riscv = "copy_bytes: beqz a2,done\nloop: lbu a3,0(a1)\nsb a3,0(a0)\naddi a0,a0,1\naddi a1,a1,1\naddi a2,a2,-1\nbnez a2,loop\ndone: ret\n"
thumb0 = ".syntax unified\n.thumb\n.thumb_func\ncopy_bytes:\ncmp r2,#0\nbeq done\nloop: ldrb r3,[r1]\nstrb r3,[r0]\nadds r0,#1\nadds r1,#1\nsubs r2,#1\nbne loop\ndone: bx lr\n"
thumb4 = ".syntax unified\n.thumb\n.thumb_func\ncopy_bytes:\ncbz r2,done\nloop: ldrb r3,[r1],#1\nstrb r3,[r0],#1\nsubs r2,#1\nbne loop\ndone: bx lr\n"
source, binary = out / "MICA.mica", out / "MICA.bin"
source.write_text(".arch mica32v2\n" + mica)
run([tools / "mica-as", "--profile", "MICA-2E", source, "-o", binary])
rows = [
    {
        "target": "MICA F+2C",
        "routine_bytes": binary.stat().st_size,
        "encoding_hex": binary.read_bytes().hex(),
        "source": source.read_text(),
        "execution": "MICA emulator and RTL cases below",
    }
]
for target, triple, features, text in (
    ("RV32I", "riscv32", [], riscv),
    ("RV32IC", "riscv32", ["-mattr=+c"], riscv),
    ("RV32IC_Zcb", "riscv32", ["-mattr=+c,+zcb"], riscv),
    ("Cortex-M0+", "thumbv6m-none-eabi", ["-mcpu=cortex-m0plus"], thumb0),
    ("Cortex-M4", "thumbv7em-none-eabi", ["-mcpu=cortex-m4"], thumb4),
):
    source, obj, raw = [out / (target + suffix) for suffix in (".s", ".o", ".bin")]
    source.write_text(".text\n" + text)
    run(
        [
            args.llvm_mc,
            "-triple=" + triple,
            *features,
            "-filetype=obj",
            source,
            "-o",
            obj,
        ]
    )
    run([args.llvm_objcopy, "-O", "binary", "--only-section=.text", obj, raw])
    rows.append(
        {
            "target": target,
            "routine_bytes": raw.stat().st_size,
            "encoding_hex": raw.read_bytes().hex(),
            "source": source.read_text(),
            "execution": "assembled, not target-executed",
        }
    )

# Validate normal memory, exact writes, zero count and return for MICA only.
cases = []
for width, profile in ((32, "MICA-2E"), (64, "MICA-2L")):
    for count in (0, 1, 7, 64, 127, 256):
        source, raw, trace = [
            out / f"copy{width}-{count}{suffix}"
            for suffix in (".mica", ".bin", ".ref.jsonl")
        ]
        data = [(index * 73 + 19) & 255 for index in range(count)]
        source.write_text(
            f".arch mica{width}v2\nli32 x1,32768\nli32 x2,33792\nli32 x3,{count}\ncall copy_bytes\nstop\n"
            + mica
            + "\n.org 33792\n.byte "
            + ",".join(map(str, data or [0]))
            + "\n"
        )
        run([tools / "mica-as", "--profile", profile, source, "-o", raw])
        run(
            [
                tools / "mica-run",
                "--profile",
                profile,
                "--memory",
                65536,
                "--retire-trace",
                trace,
                raw,
            ]
        )
        events = list(map(json.loads, trace.read_text().splitlines()))
        writes = [
            effect for event in events for effect in event["memory"] if effect["write"]
        ]
        expected = [
            {"addr": 32768 + index, "data": value, "bytes": 1, "write": True}
            for index, value in enumerate(data)
        ]
        if writes != expected or events[-1]["regs"][1:4] != [
            32768 + count,
            33792 + count,
            0,
        ]:
            raise AssertionError(
                f"copy return, pointer or byte mismatch: {width}/{count}"
            )
        # The independently checked memory oracle also anchors the RTL comparison.
        actual = trace.with_name(trace.stem + ".rtl.jsonl")
        metrics = []
        for seed in (1, 17, 1234):
            result = run(
                [ROOT / f"build/rtl/{profile}-reuse1/Vmica_core_txn", raw, actual, seed]
            )
            compare(trace, actual, f"copy-routine/{width}/{count}/{seed}")
            metrics.append(json.loads(result.stderr))
        cases.append(
            {
                "xlen": width,
                "count": count,
                "retired": sum(event["retired"] for event in events),
                "rtl_runs": metrics,
            }
        )
report = {
    "method": "handwritten equivalent complete byte-copy routines including zero-count guard and return; arguments are destination/source/count and are advanced by count; no overlap guarantee",
    "limits": "A routine encoding comparison, not complete compiler-generated firmware. Competitor images are not executed. No external cycle, area, timing or energy comparison. Custom ISA extensions beyond named profiles are excluded.",
    "llvm": run([args.llvm_mc, "--version"]).stdout.splitlines()[0],
    "measurements": rows,
    "mica_execution": cases,
}
(out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
print(
    "PASS complete copy routines:",
    {row["target"]: row["routine_bytes"] for row in rows},
)
