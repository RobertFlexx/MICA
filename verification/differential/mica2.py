#!/usr/bin/env python3
"""Compare MICA 2.0 RTL retirement with the interpreter under bus stalls."""

import argparse
import json
from pathlib import Path
import subprocess

from run import checked, compare

ROOT = Path(__file__).resolve().parents[2]


def cases(width, trap):
    code = [f".arch mica{width}v2", "li32 sp,32768", "li8 x1,91"]
    for slot in range(8):
        offset = slot * (width // 8)
        code += [f"stsp x1,[sp+{offset}]", f"ldsp x2,[sp+{offset}]", "addi x1,-7"]
    code += ["stsp x0,[sp]", "ldsp x0,[sp]", "stsp sp,[sp]", "ldsp sp,[sp]"]
    for displacement in [-32768, -1, 0, 1, 32767]:
        code += [f"adrpc x3,{displacement}"]
    code += ["li8 x1,0", "dbnz.s x1,wrapped", "li8 x2,-1", "wrapped: stop"]
    yield "slots-address-wrap", "\n".join(code) + "\n", None
    yield "branch-backward-limit", (
        f".arch mica{width}v2\nli8 x1,2\nb branch\n"
        "target: addi x2,1\n" + "nop\n" * 30 + "branch: dbnz.s x1,target\nstop\n"
    ), None
    yield "branch-forward-limit", (
        f".arch mica{width}v2\nli8 x1,2\ndbnz.s x1,target\n"
        + "nop\n" * 31
        + "target: stop\n"
    ), None
    yield "short-loop", (ROOT / f"examples/mica2_short{width}.mica").read_text(), None
    yield "sleep-external-wake", f".arch mica{width}v2\nwfi\nli8 x1,42\nstop\n", 1
    top = (1 << width) - width // 8
    yield "stack-address-wrap", (
        f".arch mica{width}v2\nli{width} sp,{top}\nldsp x2,[sp+{width // 8}]\nstop\n"
    ), None
    if width == 64:
        yield "word-sign-extension", (
            ".arch mica64v2\nli32 x1,0x80000000\nstw x1,[sp]\n"
            "ldw x2,[sp]\nldwu x3,[sp]\nli32 x1,0xffffffff\n"
            "stw x1,[sp]\nldw x4,[sp]\nstop\n"
        ), None
    if not trap:
        return
    yield "upper-registers", f".arch mica{width}v2\nadrpc x15,-1\nadd3 x8,x15,x15\nstop\n", None
    for unit, stride in [("b", 1), ("w", 4)]:
        yield f"flow-{unit}-copy", (
            f".arch mica{width}v2\nli32 x1,32768\nli32 x2,32800\nli8 x3,4\n"
            f"loop: ldpi.{unit} x4,[x2]\nstpi.{unit} x4,[x1]\ndbnz.s x3,loop\nstop\n"
            + ".org 32800\n"
            + (".byte 11,22,33,44\n" if stride == 1 else ".word 11,22,33,44\n")
        ), None
    for name, instruction in [
        ("misaligned-stack-load", "li32 sp,32769\nldsp x1,[sp]"),
        ("misaligned-stack-store", "li32 sp,32769\nstsp x1,[sp]"),
        ("unmapped-stack-load", "li32 sp,0x40000000\nldsp x1,[sp]"),
        ("unmapped-zero-load", "li32 sp,0x40000000\nldsp x0,[sp]"),
        ("unmapped-stack-store", "li32 sp,0x40000000\nstsp x1,[sp]"),
        ("reserved-stop", ".half 0x0a48"),
        ("zero-counter", ".half 0x0840"),
        ("ecall-pc", "ecall"),
    ]:
        yield name, (
            f".arch mica{width}v2\nli32 x5,handler\ncsrw tvec,x5\nli8 x1,55\n"
            + instruction
            + "\nstop\nhandler: csrr x2,epc\ncsrr x3,cause\ncsrr x4,tval\nstop\n"
        ), None
    yield "sleep-interrupt-handler", (
        f".arch mica{width}v2\nli32 x5,handler\ncsrw tvec,x5\n"
        "li8 x1,1\ncsrw ie,x1\ncsrw status,x1\nwfi\nli8 x1,42\nstop\n"
        "handler: li8 x3,99\ncsrw ip,x0\neret\n"
    ), 6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, default=ROOT / "build")
    parser.add_argument("--rtl", type=Path, default=ROOT / "build/rtl")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "build/differential-mica2"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    profiles = json.loads((ROOT / "isa/profiles/profiles.json").read_text())["profiles"]
    report = []
    for name in ["MICA-2C", "MICA-2E", "MICA-2L"]:
        width = profiles[name]["xlen"]
        driver = args.rtl / f"{name}-reuse1/Vmica_core_txn"
        flags = ["--profile", name]
        for case, source, irq in cases(width, "T" in profiles[name]["extensions"]):
            stem = args.output / f"{name}-{case}"
            path, binary, reference, actual = [
                stem.with_suffix(s)
                for s in [".mica", ".bin", ".ref.jsonl", ".rtl.jsonl"]
            ]
            path.write_text(source)
            checked([args.tools / "mica-as", *flags, path, "-o", binary])
            if irq:
                probe = subprocess.run(
                    [
                        str(args.tools / "mica-run"),
                        *flags,
                        "--steps",
                        "500",
                        "--retire-trace",
                        str(reference),
                        str(binary),
                    ],
                    capture_output=True,
                    text=True,
                )
                if probe.returncode == 0 or "step limit exceeded" not in probe.stderr:
                    raise AssertionError("WFI did not sleep before the wake event")
                events = [
                    json.loads(line) for line in reference.read_text().splitlines()
                ]
                irq = sum(event["retired"] for event in events)
                if events[-1]["insn"] != 0x480:
                    raise AssertionError("last event before sleep was not WFI")
            wake = ["--irq-at", irq] if irq else []
            checked(
                [
                    args.tools / "mica-run",
                    *flags,
                    *wake,
                    "--memory",
                    "65536",
                    "--steps",
                    "20000",
                    "--retire-trace",
                    reference,
                    binary,
                ]
            )
            for seed in [1, 17, 1234]:
                result = checked([driver, binary, actual, seed, 0, 0, irq or 0, 20])
                count = compare(reference, actual, f"{name}/{case}/{seed}")
                report.append(
                    {
                        "profile": name,
                        "case": case,
                        "seed": seed,
                        "events": count,
                        **json.loads(result.stderr),
                    }
                )
            if case == "short-loop":
                for reset in [5, 13, 51]:
                    checked([driver, binary, actual, 17, reset])
                    compare(reference, actual, f"{name}/reset-{reset}")
            print(f"PASS {name}: {case}", flush=True)
    (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS {len(report)} MICA 2.0 differential runs plus 9 reset replays")


if __name__ == "__main__":
    main()
