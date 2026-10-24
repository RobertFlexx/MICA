#!/usr/bin/env python3
"""Execute an explicit conformance case for every allocated instruction."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "verification/differential"))
from run import checked, compare

FLAGS = ["--mica2", "--xreg", "--mul", "--flow", "--bitops", "--trap"]


def instruction(group, row):
    name, op = row["name"], row["op"]
    if group == "R":
        args = (
            ""
            if op == 0 or 18 <= op <= 22
            else "x5" if op in (13, 14) else "x1" if op in (15, 16) else "x1,x2"
        )
    elif group == "I":
        args = "done" if op == 7 else "x1,done" if op in (5, 6) else "x1,3"
    elif group in ("MEM", "MX"):
        args = "x1,[x4]"
    elif group in ("ALU", "W32"):
        args = "x3,x1,x2"
    elif group == "IMM":
        args = "x3,x1,3"
    elif group == "WIDE":
        args = "x3,3"
    elif group == "BR":
        args = "x1,x2,done"
    elif group == "J":
        args = "done"
    elif group == "LOOP":
        args = "x2,done"
    elif group == "FLOW":
        args = "x1,[x4],-8"
    elif group == "BITOPS":
        args = "x3,x1" if op <= 3 or op >= 17 else "x3,x1,x2"
    elif group == "SYS":
        args = (
            "x3,coreid"
            if op == 0
            else "status,x2" if op == 1 else "x3,[x4]" if op in (2, 6) else "x3,x2,[x4]"
        )
    elif group == "V":
        if op in (16, 17):
            args = "v3,[x4]"
        else:
            name += ".s8" if op == 15 else ".s16"
            args = "v3,v1" if op in (13, 14) else "v3,v1,v2"
    elif group == "2C":
        args = (
            "x1,[sp]"
            if name in ("ldsp", "stsp")
            else "x2,done" if name == "dbnz.s" else ""
        )
    else:
        raise ValueError(group)
    return name + (" " + args if args else "")


def program(group, row, width):
    setup = [
        f".arch mica{width}v2",
        "li32 sp,32768",
        "li8 x1,-5",
        "li8 x2,3",
        "li8 x3,0",
        "li32 x4,32768",
        "li32 x5,done",
    ]
    if group == "V":
        setup += ["vld v1,[x4]", "vld v2,[x4]"]
    if row["name"] in ("sc.w", "sc.q"):
        setup += ["lr." + row["name"].split(".")[1] + " x3,[x4]"]
    operation = instruction(group, row)
    if row["name"] == "eret":
        setup += [
            "li32 x5,handler",
            "csrw tvec,x5",
            "ecall",
            "b done",
            "handler: csrr x5,epc",
            "addi x5,2",
            "csrw epc,x5",
        ]
    elif row["name"] == "ecall":
        setup += ["li32 x5,done", "csrw tvec,x5"]
    return "\n".join(
        [
            *setup,
            "under_test:",
            operation,
            "done: stop",
            ".org 32768",
            ".quad 0x80ff1234ff800001,0x7fff80007fff8000",
            "",
        ]
    )


def rows():
    spec = json.loads((ROOT / "isa/encodings/mica2.json").read_text())
    for group, entries in spec["groups"].items():
        if group != "CSRS":
            for row in entries:
                yield group, row
    compact = json.loads((ROOT / "isa/encodings/mica2-compact.json").read_text())
    for name in compact["opcodes"]:
        yield "2C", {"name": name, "op": 0, "extension": "2C"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, default=ROOT / "build")
    parser.add_argument(
        "--rtl", type=Path, help="require MICA-2E/2L retirement drivers"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "build/instructions")
    parser.add_argument(
        "--report", type=Path, help="write the instruction completion matrix"
    )
    parser.add_argument(
        "--check-report", type=Path, help="reject a stale checked-in matrix"
    )
    args = parser.parse_args()
    args.tools = args.tools.resolve()
    if args.rtl:
        args.rtl = args.rtl.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    result = []
    for group, row in rows():
        widths = (
            [64] if group in ("MX", "W32") or row["name"].endswith(".q") else [32, 64]
        )
        entry = {
            "instruction": row["name"],
            "group": group,
            "extension": row["extension"],
            "assembler": True,
            "disassembler": True,
            "emulator": True,
            "rtl": None,
            "cases": [],
        }
        software_only = row["extension"] in ("A", "V")
        for width in widths:
            stem = args.output / f"{group}-{row['name']}-{width}"
            source, binary, symbols, ref, actual = [
                Path(str(stem) + ext)
                for ext in (".mica", ".bin", ".map", ".ref.jsonl", ".rtl.jsonl")
            ]
            source.write_text(program(group, row, width))
            flags = [
                *FLAGS,
                "--xlen",
                width,
                *(["--atomic", "--simd"] if software_only else []),
            ]
            checked(
                [args.tools / "mica-as", *flags, source, "-o", binary, "--map", symbols]
            )
            address = next(
                int(line.split()[0], 16)
                for line in symbols.read_text().splitlines()
                if line.split()[1] == "under_test"
            )
            listing = checked(
                [args.tools / "mica-dis", "--xlen", width, "--mica2", binary]
            ).stdout
            line = next(
                line for line in listing.splitlines() if line.split()[0] == hex(address)
            )
            if line.split()[1].split(",")[0] != instruction(group, row).split()[0]:
                raise AssertionError(f"{row['name']}: incorrect disassembly: {line}")
            wake = []
            if row["name"] == "wfi":
                probe = subprocess.run(
                    [
                        str(x)
                        for x in [
                            args.tools / "mica-run",
                            *flags,
                            "--steps",
                            200,
                            "--retire-trace",
                            ref,
                            binary,
                        ]
                    ],
                    capture_output=True,
                    text=True,
                )
                if probe.returncode == 0 or "step limit exceeded" not in probe.stderr:
                    raise AssertionError("WFI did not sleep")
                count = sum(
                    json.loads(line)["retired"] for line in ref.read_text().splitlines()
                )
                wake = ["--irq-at", count]
            checked(
                [
                    args.tools / "mica-run",
                    *flags,
                    *wake,
                    "--memory",
                    65536,
                    "--steps",
                    1000,
                    "--retire-trace",
                    ref,
                    binary,
                ]
            )
            events = [json.loads(line) for line in ref.read_text().splitlines()]
            if not any(e["pc"] == address and e["retired"] for e in events):
                raise AssertionError(f"{row['name']}: instruction was not executed")
            case = {"xlen": width, "events": len(events), "rtl_seeds": []}
            if args.rtl and not software_only:
                driver = (
                    args.rtl
                    / f"MICA-2{'L' if width == 64 else 'E'}-reuse1/Vmica_core_txn"
                )
                for seed in (1, 17, 1234):
                    checked(
                        [
                            driver,
                            binary,
                            actual,
                            seed,
                            0,
                            0,
                            wake[-1] if wake else 0,
                            20,
                        ]
                    )
                    compare(ref, actual, f"{row['name']}/{width}/{seed}")
                    case["rtl_seeds"].append(seed)
                entry["rtl"] = True
            entry["cases"].append(case)
        entry["status"] = "Software only" if software_only else "Experimental"
        result.append(entry)
        print(f"PASS {row['name']}: {entry['status']}", flush=True)
    report = {
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [
                ROOT / "isa/encodings/mica2.json",
                ROOT / "rtl/mica_core_txn.sv",
                ROOT / "sim/emulator.cpp",
                ROOT / "toolchain/assembler.cpp",
            ]
        },
        "instructions": result,
    }
    (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    if args.report or args.check_report:
        text = "# Instruction implementation matrix\n\n"
        text += "Generated by `verification/instructions/run.py` from executed assembly, disassembly, interpreter and RTL retirement tests. Scalar instructions remain experimental: the vectors establish integration, not exhaustive semantic, fault or interrupt coverage. Coverage limits are documented in [COVERAGE.md](COVERAGE.md). A and V remain software-only.\n\n"
        text += "| Instruction | Extension | XLEN | Assembler | Disassembler | Emulator | RTL | Status |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        for row in result:
            text += f"| `{row['instruction']}` | {row['extension']} | {','.join(str(c['xlen']) for c in row['cases'])} | Pass | Pass | Pass | {'Pass' if row['rtl'] else 'Not implemented' if row['status'] == 'Software only' else 'Not run'} | {row['status']} |\n"
        if args.check_report:
            if args.check_report.read_text() != text:
                raise SystemExit("stale instruction matrix: " + str(args.check_report))
        else:
            args.report.write_text(text)
    print(f"PASS {len(result)} instruction entries")


if __name__ == "__main__":
    main()
