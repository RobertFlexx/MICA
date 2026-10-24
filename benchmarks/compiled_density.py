#!/usr/bin/env python3
"""Measure complete ROM images from the same C program at frontend -O0."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tools", type=Path, default=ROOT / "build")
parser.add_argument("--clang", default="clang")
parser.add_argument("--output", type=Path, default=ROOT / "build/compiled-density")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
tools = args.tools.resolve()


def run(command, required=True):
    result = subprocess.run(
        [str(x) for x in command], capture_output=True, text=True, timeout=60
    )
    with (out / "commands.log").open("a") as log:
        log.write(
            repr([str(x) for x in command]) + "\n" + result.stdout + result.stderr
        )
    if required and result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result


(out / "commands.log").write_text("")
sources = [ROOT / "compiler/tests/program.c", ROOT / "compiler/tests/library.c"]
rows = []
for profile in ("MICA-2C", "MICA-2E"):
    objects = []
    for source in sources:
        obj = out / (profile + "-" + source.stem + ".o")
        run(
            [
                sys.executable,
                ROOT / "compiler/mica_cc.py",
                source,
                "--clang",
                args.clang,
                "--assembler",
                tools / "mica-as",
                "--profile",
                profile,
                "-o",
                obj,
            ]
        )
        objects.append(obj)
    startup = out / "mica-start.mica"
    startup.write_text(
        ".arch mica32v2\n.global _start\n.extern main\n_start: li32 sp,65520\ncall main\nstop\n"
    )
    start = out / (profile + "-start.o")
    run([tools / "mica-as", "--profile", profile, "-c", startup, "-o", start])
    binary, elf = out / (profile + ".bin"), out / (profile + ".elf")
    run([tools / "mica-ld", start, *objects, "-o", binary, "--elf", elf])
    execution = run([tools / "mica-run", "--profile", profile, "--memory", 65536, elf])
    if "x1=0x42" not in execution.stderr:
        raise AssertionError("compiled benchmark result must be 66")
    rows.append(
        {
            "target": profile,
            "status": "measured",
            "rom_bytes": binary.stat().st_size,
            "executed": True,
            "backend": "MICA experimental IR lowering",
        }
    )

link = out / "memory.ld"
link.write_text(
    "ENTRY(_start)\nSECTIONS { . = 0; .text : { *(.text*) *(.rodata*) } "
    ". = ALIGN(4); .data : { *(.data*) *(.sdata*) } .bss (NOLOAD) : { *(.bss*) *(.sbss*) *(COMMON) } "
    "/DISCARD/ : { *(.comment) *(.note*) *(.riscv.attributes) *(.ARM.attributes) *(.ARM.exidx*) } }\n"
)
targets = [
    ("RV32I", "riscv32-unknown-elf", ["-march=rv32i", "-mabi=ilp32"], False),
    ("RV32IC", "riscv32-unknown-elf", ["-march=rv32ic", "-mabi=ilp32"], False),
    ("RV32EC", "riscv32-unknown-elf", ["-march=rv32ec", "-mabi=ilp32e"], False),
    ("RV32IC_Zcb", "riscv32-unknown-elf", ["-march=rv32ic_zcb", "-mabi=ilp32"], False),
    (
        "Cortex-M0+",
        "thumbv6m-none-eabi",
        ["-mcpu=cortex-m0plus", "-mthumb", "-mfloat-abi=soft"],
        True,
    ),
    (
        "Cortex-M4",
        "thumbv7em-none-eabi",
        ["-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=soft"],
        True,
    ),
]
for name, target, flags, arm in targets:
    start = out / (name + ".s")
    start.write_text(
        (
            ".syntax unified\n.thumb\n.global _start\n.thumb_func\n_start:\nldr r0,=65520\nmov sp,r0\nbl main\nbkpt #0\n.align 2\n"
            if arm
            else ".global _start\n_start:\nlui sp,16\naddi sp,sp,-16\njal ra,main\nebreak\n"
        )
    )
    elf, binary = out / (name + ".elf"), out / (name + ".bin")
    result = run(
        [
            args.clang,
            "--target=" + target,
            *flags,
            "-O0",
            "-ffreestanding",
            "-fno-builtin",
            "-fno-unwind-tables",
            "-fno-asynchronous-unwind-tables",
            "-nostdlib",
            "-fuse-ld=lld",
            "-Wl,-T," + str(link),
            *([] if arm else ["-Wl,--no-relax"]),
            start,
            *sources,
            "-o",
            elf,
        ],
        required=False,
    )
    if result.returncode:
        if name != "RV32EC":
            raise RuntimeError(result.stderr)
        rows.append(
            {
                "target": name,
                "status": "tool unsupported",
                "diagnostic": result.stderr.strip(),
            }
        )
        continue
    run(["llvm-objcopy", "-O", "binary", elf, binary])
    rows.append(
        {
            "target": name,
            "status": "measured",
            "rom_bytes": binary.stat().st_size,
            "executed": False,
            "backend": "Clang target backend",
        }
    )
report = {
    "clang": run([args.clang, "--version"]).stdout.splitlines()[0],
    "program": "compiler/tests/program.c + library.c: array sum, structure, conditional, cross-object call and recursion",
    "method": "Identical C input, -O0 frontend, explicit startup and flat ROM layout from address zero, 64 KiB SRAM stack. Includes code, constants, initialized data and alignment; excludes ELF container/debug metadata. No LTO or dead-code elimination.",
    "limits": "MICA uses stack homes and a small local high-register allocator; allocation and optimization differ from the other backends. These are prototype code-generation results, not ISA density rankings. Competitor images are built but not target-executed. No competitor cycles, area or energy measured.",
    "results": rows,
}
(out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
for row in rows:
    print(row["target"], row.get("rom_bytes", row["status"]))
