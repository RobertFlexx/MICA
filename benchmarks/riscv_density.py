#!/usr/bin/env python3
"""Assemble equivalent loop bodies for MICA 2.0, RISC-V and Thumb.

Measures emitted instruction bytes, excluding setup and termination. No clock,
power, compiler-quality or whole-program advantage is inferred from these loops.
"""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
KERNELS = {
    "counted-branch": (
        "loop: dbnz.s x3,loop\n",
        [],
        "loop: addi a2,a2,-1\nbnez a2,loop\n",
        1,
        2,
    ),
    "byte-copy": (
        "loop: ldpi.b x4,[x2]\nstpi.b x4,[x1]\ndbnz.s x3,loop\n",
        ["--flow"],
        "loop: lbu a3,0(a1)\nsb a3,0(a0)\naddi a0,a0,1\naddi a1,a1,1\naddi a2,a2,-1\nbnez a2,loop\n",
        3,
        6,
    ),
    "word-copy": (
        "loop: ldpi.w x4,[x2]\nstpi.w x4,[x1]\ndbnz.s x3,loop\n",
        ["--flow"],
        "loop: lw a3,0(a1)\nsw a3,0(a0)\naddi a0,a0,4\naddi a1,a1,4\naddi a2,a2,-1\nbnez a2,loop\n",
        3,
        6,
    ),
    "stack-roundtrip": (
        "stsp x1,[sp]\nldsp x1,[sp]\n",
        [],
        "sw a0,0(sp)\nlw a0,0(sp)\n",
        2,
        2,
    ),
}
THUMB = {
    "counted-branch": (
        "loop:\nsubs r2,#1\nbne loop\n",
        "loop:\nsubs r2,#1\nbne loop\n",
    ),
    "byte-copy": (
        "loop:\nldrb r3,[r1]\nstrb r3,[r0]\nadds r0,#1\nadds r1,#1\nsubs r2,#1\nbne loop\n",
        "loop:\nldrb r3,[r1],#1\nstrb r3,[r0],#1\nsubs r2,#1\nbne loop\n",
    ),
    "word-copy": (
        "loop:\nldr r3,[r1]\nstr r3,[r0]\nadds r0,#4\nadds r1,#4\nsubs r2,#1\nbne loop\n",
        "loop:\nldr r3,[r1],#4\nstr r3,[r0],#4\nsubs r2,#1\nbne loop\n",
    ),
    "stack-roundtrip": (
        "str r0,[sp]\nldr r0,[sp]\n",
        "str r0,[sp]\nldr r0,[sp]\n",
    ),
}


def checked(command):
    return subprocess.run(
        [str(x) for x in command], check=True, capture_output=True, text=True
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assembler", type=Path, default=ROOT / "build/mica-as")
    parser.add_argument("--emulator", type=Path, default=ROOT / "build/mica-run")
    parser.add_argument("--llvm-mc", default="llvm-mc")
    parser.add_argument("--llvm-objcopy", default="llvm-objcopy")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "build/riscv-density/results.json"
    )
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory(prefix="mica-riscv-density-") as temp:
        stage = Path(temp)
        for name, (mica, flags, riscv, mica_count, rv_count) in KERNELS.items():
            source, binary = stage / "kernel.mica", stage / "kernel.bin"
            source.write_text(".arch mica32v2\n" + mica)
            checked([args.assembler, "--mica2", *flags, source, "-o", binary])
            size = binary.stat().st_size
            row = {
                "kernel": name,
                "mica_bytes": size,
                "mica_instructions": mica_count,
                "riscv_instructions": rv_count,
                "mica_source": source.read_text(),
                "riscv_source": riscv,
                "riscv": {},
            }
            rv_source, obj, raw = (
                stage / "kernel.s",
                stage / "kernel.o",
                stage / "kernel.rv.bin",
            )
            rv_source.write_text(".text\n" + riscv)
            for profile, features in [
                ("RV32I", []),
                ("RV32IC", ["-mattr=+c"]),
                ("RV32IC_Zcb", ["-mattr=+c,+zcb"]),
            ]:
                checked(
                    [
                        args.llvm_mc,
                        "-triple=riscv32",
                        "-filetype=obj",
                        *features,
                        rv_source,
                        "-o",
                        obj,
                    ]
                )
                checked(
                    [
                        args.llvm_objcopy,
                        "-O",
                        "binary",
                        "--only-section=.text",
                        obj,
                        raw,
                    ]
                )
                rv_size = raw.stat().st_size
                row["riscv"][profile] = {
                    "bytes": rv_size,
                    "encoding_hex": raw.read_bytes().hex(),
                    "mica_reduction_percent": round(
                        100 * (rv_size - size) / rv_size, 3
                    ),
                }
            row["thumb"] = {}
            for profile, (triple, cpu, source_text) in {
                "Thumb_M0+": ("thumbv6m", "cortex-m0plus", THUMB[name][0]),
                "Thumb_M4": ("thumbv7m", "cortex-m4", THUMB[name][1]),
            }.items():
                thumb_source = stage / "kernel-thumb.s"
                thumb_source.write_text(".syntax unified\n.thumb\n" + source_text)
                checked(
                    [
                        args.llvm_mc,
                        "-triple=" + triple,
                        "-mcpu=" + cpu,
                        "-filetype=obj",
                        thumb_source,
                        "-o",
                        obj,
                    ]
                )
                checked(
                    [
                        args.llvm_objcopy,
                        "-O",
                        "binary",
                        "--only-section=.text",
                        obj,
                        raw,
                    ]
                )
                row["thumb"][profile] = {
                    "bytes": raw.stat().st_size,
                    "encoding_hex": raw.read_bytes().hex(),
                    "source": thumb_source.read_text(),
                }
            rows.append(row)
            print(
                name,
                "MICA:",
                size,
                "RISC-V:",
                {k: v["bytes"] for k, v in row["riscv"].items()},
                "Thumb:",
                {k: v["bytes"] for k, v in row["thumb"].items()},
            )
        # Execute complete MICA copy programs and inspect every copied word.
        # RISC-V is assembled and sized above; it is not run on a RISC-V CPU.
        for width in [32, 64]:
            for unit in ["b", "w"]:
                stride = 1 if unit == "b" else 4
                source.write_text(
                    f".arch mica{width}v2\nli32 x1,32768\nli32 x2,32800\n"
                    "li8 x3,4\n"
                    + f"loop: ldpi.{unit} x4,[x2]\nstpi.{unit} x4,[x1]\ndbnz.s x3,loop\n"
                    + "li32 x1,32768\n"
                    + "\n".join(
                        f"ld{'bu' if unit == 'b' else 'w'} x{reg},[x1+{(reg-2)*stride}]"
                        for reg in range(2, 6)
                    )
                    + "\nstop\n.org 32800\n"
                    + (".byte 11,22,33,44\n" if unit == "b" else ".word 11,22,33,44\n")
                )
                checked(
                    [
                        args.assembler,
                        "--mica2",
                        "--flow",
                        "--xlen",
                        width,
                        source,
                        "-o",
                        binary,
                    ]
                )
                run = checked(
                    [args.emulator, "--mica2", "--flow", "--xlen", width, binary]
                )
                for reg, value in zip(range(2, 6), [11, 22, 33, 44]):
                    if f"x{reg}=0x{value:x}" not in run.stderr:
                        raise SystemExit(
                            "copy kernel verification failed: " + run.stderr
                        )
    report = {
        "method": "LLVM and MICA assembler output; loop bodies only, hand-written and register-constrained; MICA copy programs executed at XLEN32/64",
        "limits": "RISC-V and Thumb execution, compiler output, synthesized cross-ISA area, routed timing and measured energy are not compared. Zcb is enabled explicitly. Thumb-M0+ uses separate load, store and pointer updates. Thumb-M4 uses post-indexed loads and stores where that encoding exists. Custom hardware-loop extensions are outside this comparison.",
        "llvm": checked([args.llvm_mc, "--version"]).stdout.splitlines()[0],
        "measurements": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
