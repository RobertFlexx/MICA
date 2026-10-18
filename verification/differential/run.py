#!/usr/bin/env python3
"""Compare architectural events, reporting the first divergence and preserving artifacts."""

import argparse
import json
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parents[2]
FLAGS = ["--xreg", "--mul", "--flow", "--bitops", "--trap"]


def checked(command, **kwargs):
    p = subprocess.run(
        [str(x) for x in command], capture_output=True, text=True, timeout=90, **kwargs
    )
    if p.returncode:
        raise RuntimeError(f"{command}\n{p.stdout}\n{p.stderr}")
    return p


def compare(reference, implementation, name):
    a = [json.loads(x) for x in reference.read_text().splitlines()]
    b = [json.loads(x) for x in implementation.read_text().splitlines()]
    if len(a) != len(b):
        raise AssertionError(
            f"{name}: event count {len(a)} != {len(b)}; inspect {implementation}"
        )
    for i, (left, right) in enumerate(zip(a, b)):
        for key in (
            "order",
            "pc",
            "insn",
            "length",
            "retired",
            "next_pc",
            "trap",
            "cause",
            "regs",
            "memory",
        ):
            if left[key] != right[key]:
                raise AssertionError(
                    f"{name}: event {i} pc={left['pc']:#x} {key}\nreference: {left[key]}\nRTL: {right[key]}\n{implementation}"
                )
    return len(a)


def random_program(width, seed):
    rng = random.Random(seed)
    groups = json.loads((ROOT / "isa/encodings/mica2.json").read_text())["groups"]
    out = [f".arch mica{width}", "li32 x7, 65520"]
    for reg in range(1, 16):
        if reg != 7:
            out.append(
                f"li{'64' if width == 64 else '32'} x{reg}, {rng.getrandbits(width)}"
            )
    for group in ["ALU", "IMM", "BITOPS"] + (["W32"] if width == 64 else []):
        for row in groups[group] * 4:
            d = rng.choice([r for r in range(16) if r != 7])
            a, b = rng.randrange(16), rng.randrange(16)
            if group == "IMM":
                value = (
                    rng.randrange(width)
                    if row["op"] >= 4
                    else (
                        rng.randrange(-8192, 8192)
                        if row["op"] == 0
                        else rng.randrange(16384)
                    )
                )
                out.append(f"{row['name']} x{d},x{a},{value}")
            elif group == "BITOPS" and (row["op"] <= 3 or row["op"] >= 17):
                out.append(f"{row['name']} x{d},x{a}")
            else:
                out.append(f"{row['name']} x{d},x{a},x{b}")
    for row in groups["R"]:
        op = row["op"]
        if op in [0, 19, 22]:
            out.append(row["name"])
        elif op in [15, 16]:
            out.append(f"{row['name']} x1")
        elif 1 <= op <= 12 or op == 17:
            out.append(f"{row['name']} x1,x2")
    out += [
        "li32 x5,short_call",
        "jalr x5",
        "b short_done",
        "short_call: addi x2,1",
        "ret",
        "short_done:",
    ]
    out += ["li32 x5, 32768", "li32 x1, 0x8765fedc"]
    for offset in range(-16, 17, 4):
        out += [f"stw x1,[x5{offset:+}]", f"ldw x2,[x5{offset:+}]"]
    for load, store, scale in [
        ("ldbu", "stb", 1),
        ("ldb", "stb", 1),
        ("ldhu", "sth", 2),
        ("ldh", "sth", 2),
    ]:
        for offset in [-scale, 0, scale]:
            out += [f"{store} x1,[x5{offset:+}]", f"{load} x2,[x5{offset:+}]"]
    if width == 64:
        for load in ["ldq", "ldws", "ldwu", "ldbs", "ldhs"]:
            out += ["stq x1,[x5-8]", f"{load} x2,[x5-8]"]
    for suffix in ["b", "h", "w"] + (["q"] if width == 64 else []):
        out += [
            "li32 x5,32768",
            f"stpi.{suffix} x1,[x5]",
            "li32 x5,32768",
            f"ldpi.{suffix} x2,[x5]",
            "li32 x5,32776",
            f"stpi.{suffix} x1,[x5],-8",
            f"ldpi.{suffix} x2,[x5],0",
        ]
    out += [
        "li8 x3,7",
        "loop: addi x1,1",
        "dbnz x3,loop",
        "call routine",
        "wfi",
        "routine: addi x2,-1",
        "ret",
    ]
    return "\n".join(out) + "\n"


def fault_program(width, instruction):
    return f""".arch mica{width}
li32 x5,handler
csrw tvec,x5
li8 x1,55
{instruction}
wfi
handler:
csrr x2,epc
csrr x3,cause
csrr x4,tval
wfi
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tools", type=Path, default=ROOT / "build")
    p.add_argument("--rtl", type=Path, default=ROOT / "build/rtl")
    p.add_argument("--output", type=Path, default=ROOT / "build/differential")
    p.add_argument("--reuse", type=int, default=1)
    p.add_argument("--quick", action="store_true")
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = []
    for width in [32, 64]:
        rtl = args.rtl / f"x{width}-reuse{args.reuse}" / "Vmica_core_txn"
        flags = ["--xlen", str(width), *FLAGS]
        cases = [
            (f"random-{seed}", random_program(width, seed))
            for seed in range(1 if args.quick else 4)
        ]
        for stem in [
            f"arithmetic{width}",
            f"flow_copy{width}",
            f"bitops{width}",
            f"arena{width}",
            f"console{width}",
            f"div{width}",
        ]:
            cases.append((stem, ROOT / "examples" / (stem + ".mica")))
        if width == 32:
            cases.extend(
                (name, ROOT / "examples" / (name + ".mica"))
                for name in ["trap32", "trap_irq32", "string32", "reduce32", "fir32"]
            )
        for name, insn in [
            ("misaligned-load", "ldw x1,[x1]"),
            ("misaligned-store", "stw x1,[x1]"),
            ("odd-jump", "jalr x1"),
            ("access-load", "li32 x5,0x40000000\nldw x1,[x5]"),
            ("access-store", "li32 x5,0x40000000\nstpi.w x1,[x5]"),
            ("access-fetch", "li32 x1,70000\njr x1"),
            ("readonly-csr", "csrw features,x1"),
            ("reserved-csr", "csrr x1,255"),
            ("reserved-shift", ".half 0x5920"),
            ("reserved-unary", ".half 0x03c9"),
        ]:
            cases.append((name, fault_program(width, insn)))
        for opcode in range(31, 256, 17 if args.quick else 1):
            cases.append(
                (f"illegal-op{opcode}", fault_program(width, f".half {opcode << 6}"))
            )
        for name, source in cases:
            stem = args.output / f"{width}-{name}"
            path = source if isinstance(source, Path) else stem.with_suffix(".mica")
            if not isinstance(source, Path):
                path.write_text(source)
            binary, ref, actual = (
                stem.with_suffix(s) for s in [".bin", ".ref.jsonl", ".rtl.jsonl"]
            )
            checked([args.tools / "mica-as", *flags, path, "-o", binary])
            checked(
                [
                    args.tools / "mica-run",
                    *flags,
                    "--memory",
                    "65536",
                    "--steps",
                    "200000",
                    "--retire-trace",
                    ref,
                    binary,
                ]
            )
            seeds = [1] if args.quick else [1, 17, 1234]
            for seed in seeds:
                result = checked([rtl, binary, actual, seed])
                events = compare(ref, actual, f"{width}/{name}/seed{seed}")
                metrics = json.loads(result.stderr)
                report.append(
                    {
                        "xlen": width,
                        "name": name,
                        "seed": seed,
                        "events": events,
                        **metrics,
                    }
                )
            if name == "arithmetic" + str(width):
                for reset_cycle in [5, 13, 51]:
                    checked([rtl, binary, actual, 17, reset_cycle])
                    compare(ref, actual, f"reset cycle {reset_cycle}")
        irq_source = f""".arch mica{width}
li32 x5,irq_handler
csrw tvec,x5
li8 x1,1
csrw ie,x1
csrw status,x1
li32 x2,32768
li8 x3,42
stw x3,[x2]
ldw x4,[x2]
addi x4,1
wfi
irq_handler:
csrw ip,x0
addi x3,1
 eret
"""
        irq_path = args.output / f"{width}-external-irq.mica"
        irq_path.write_text(irq_source)
        irq_binary, irq_reference, irq_actual = [
            irq_path.with_suffix(s) for s in [".bin", ".ref.jsonl", ".rtl.jsonl"]
        ]
        checked([args.tools / "mica-as", *flags, irq_path, "-o", irq_binary])
        checked(
            [
                args.tools / "mica-run",
                *flags,
                "--memory",
                "65536",
                "--retire-trace",
                irq_reference,
                irq_binary,
            ]
        )
        events = [json.loads(x) for x in irq_reference.read_text().splitlines()]
        memory_indices = [i + 1 for i, event in enumerate(events) if event["memory"]]
        for memory_number, retired in enumerate(memory_indices, 1):
            checked(
                [
                    args.tools / "mica-run",
                    *flags,
                    "--memory",
                    "65536",
                    "--irq-at",
                    retired,
                    "--retire-trace",
                    irq_reference,
                    irq_binary,
                ]
            )
            checked([rtl, irq_binary, irq_actual, 1234, 0, memory_number])
            compare(
                irq_reference,
                irq_actual,
                f"IRQ during memory transaction {memory_number}",
            )
        print(
            f"PASS XLEN{width}: {len(cases)} programs, randomized bus latency, reset replay"
        )
    (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS {len(report)} differential runs; artifacts in {args.output}")


if __name__ == "__main__":
    main()
