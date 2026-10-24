#!/usr/bin/env python3
"""Build compiled sensor firmware and verify its UART packets independently."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tools", type=Path, default=ROOT / "build")
parser.add_argument("--clang", default="clang")
parser.add_argument("--output", type=Path, default=ROOT / "build/sensor-demo")
args = parser.parse_args()
args.tools = args.tools.resolve()
args.output.mkdir(parents=True, exist_ok=True)


def run(command):
    result = subprocess.run([str(x) for x in command], capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result


objects = []
for name in ("sensor_node", "platform"):
    obj = args.output / (name + ".o")
    run(
        [
            sys.executable,
            ROOT / "compiler/mica_cc.py",
            "--clang",
            args.clang,
            "--assembler",
            args.tools / "mica-as",
            ROOT / f"compiler/examples/{name}.c",
            "-o",
            obj,
        ]
    )
    objects.append(obj)
startup = args.output / "startup.o"
run(
    [
        args.tools / "mica-as",
        "--profile",
        "MICA-2E",
        "-c",
        ROOT / "firmware/examples/sensor_start32.mica",
        "-o",
        startup,
    ]
)
binary, elf, symbols = [
    args.output / ("sensor-node" + ext) for ext in (".bin", ".elf", ".map")
]
run(
    [
        args.tools / "mica-ld",
        startup,
        *objects,
        "-o",
        binary,
        "--elf",
        elf,
        "--map",
        symbols,
    ]
)
expected = bytearray()
for sequence, sample in enumerate((100, 101, 102, 103)):
    crc = 0
    for byte in (sequence, sample):
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ (7 if crc & 128 else 0)) & 255
    expected.extend((165, sequence, sample, crc))
for engine in ([], ["--fast"], ["--native-loops"]):
    result = run(
        [
            args.tools / "mica-run",
            "--profile",
            "MICA-2E",
            "--watchdog",
            *engine,
            "--memory",
            65536,
            "--steps",
            100000,
            elf,
        ]
    )
    if result.stdout != expected or b"x1=0x2a" not in result.stderr:
        raise AssertionError(
            "compiled sensor UART/result mismatch: " + result.stderr.decode()
        )
run(
    [
        sys.executable,
        ROOT / "toolchain/bin2mem8.py",
        binary,
        args.output / "sensor-node.mem32",
        "--width",
        32,
        "--pad-bytes",
        65536,
    ]
)
(args.output / "expected.hex").write_text(
    "\n".join(f"{byte:02x}" for byte in expected) + "\n"
)
(args.output / "results.json").write_text(
    json.dumps(
        {
            "firmware_bytes": binary.stat().st_size,
            "expected_uart_hex": expected.hex(),
            "measurements": 4,
            "timer_delta_ticks": 2000,
            "watchdog_max_ticks": 250000,
            "emulator_engines_passed": 3,
            "limits": "Functional emulator timer ticks per executed instruction or sleep step, not RTL clocks. No physical energy model.",
        },
        indent=2,
    )
    + "\n"
)
print(
    "PASS compiled sensor: four timer wakes, CRC-8 packets, volatile MMIO and watchdog;",
    binary.stat().st_size,
    "bytes",
)
