#!/usr/bin/env python3
"""Build and validate all published assembly examples and a three-object program."""

import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--tools", type=Path, default=ROOT / "build")
p.add_argument("--output", type=Path, default=ROOT / "build/firmware")
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)


def run(tool, *args):
    r = subprocess.run(
        [str(a.tools / tool), *map(str, args)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode:
        raise RuntimeError(r.stderr)
    return r


for source in sorted((ROOT / "examples").glob("*.mica")):
    width = 64 if source.stem.endswith("64") else 32
    flags = (
        (["--mica2"] if source.stem.startswith("mica2_") else [])
        + ["--xlen", str(width), "--mul", "--flow", "--bitops", "--atomic", "--simd"]
        + (
            ["--trap"]
            if not source.stem.startswith("mica2_") or "timer" in source.stem or "watchdog" in source.stem
            else []
        )
    )
    target = a.output / (source.stem + ".bin")
    run("mica-as", *flags, source, "-o", target)
    # Macros is a dialect fragment; the LED blinker is intentionally endless.
    if source.stem not in ["macros", "fpga_blink32", "watchdog32"]:
        devices = ["--uart-input", "414243"] if source.stem == "peripherals32" else []
        if source.stem == "mica2_watchdog32":
            devices = ["--watchdog"]
        result = run(
            "mica-run",
            *flags,
            *devices,
            "--memory",
            "65536",
            "--steps",
            "500000",
            target
        )
        if source.stem == "peripherals32" and result.stdout != "ABC":
            raise AssertionError("UART/CRC peripheral firmware failed")
        if (
            source.stem in ["scheduler32", "selftest32", "peripherals32", "mica2_watchdog32"]
            and "x1=0x2a" not in result.stderr
        ):
            raise AssertionError(source.name + ": self-test failed\n" + result.stderr)
    print("PASS", source.name)
objects = []
for source in [
    ROOT / "runtime/startup/ram_start32.mica",
    ROOT / "firmware/examples/multifile_main.mica",
    ROOT / "runtime/startup/library32.mica",
]:
    obj = a.output / (source.stem + ".o")
    run("mica-as", "-c", source, "-o", obj)
    objects.append(obj)
elf, binary = a.output / "linked.elf", a.output / "linked.bin"
run(
    "mica-ld",
    *objects,
    "-T",
    ROOT / "runtime/startup/ram.ld",
    "-o",
    binary,
    "--elf",
    elf
)
result = run("mica-run", "--memory", "65536", elf)
if result.stdout != "MICA linked CRC OK\n" or "x1=0x2a" not in result.stderr:
    raise AssertionError("linked startup/CRC/UART firmware failed")
print("PASS separate startup, application, runtime -> ELF -> emulator")
