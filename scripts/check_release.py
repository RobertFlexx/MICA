#!/usr/bin/env python3
"""Extract SDK archives, exercise installed tools and optionally rebuild sources."""

import argparse
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import shutil
import sys

p = argparse.ArgumentParser()
p.add_argument("--binary", type=Path, required=True)
p.add_argument("--verbose", action="store_true", help="Show each verification command")
p.add_argument("--source", type=Path)
p.add_argument("--output", type=Path, default=Path("build/releases/validation.json"))
a = p.parse_args()
commands = []


def run(command, cwd, raw=False):
    command = [str(x) for x in command]
    if a.verbose:
        print("[release-check] " + " ".join(command), flush=True)
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=not raw, timeout=180
    )
    commands.append(
        {
            "command": command,
            "exit": result.returncode,
            "stdout": result.stdout.hex() if raw else result.stdout,
            "stderr": result.stderr.decode(errors="replace") if raw else result.stderr,
            "stdout_encoding": "hex" if raw else "text",
        }
    )
    if result.returncode:
        raise SystemExit(
            (result.stdout + result.stderr).decode(errors="replace")
            if raw
            else result.stdout + result.stderr
        )
    return result


def extract(path, destination):
    with tarfile.open(path.resolve(), "r:gz") as archive:
        members = archive.getmembers()
        if (
            len(members) > 10000
            or sum(member.size for member in members) > 512 * 1024 * 1024
        ):
            raise SystemExit("archive exceeds smoke-test resource limit")
        for member in members:
            if (
                member.name.startswith("/")
                or ".." in Path(member.name).parts
                or not (member.isdir() or member.isfile())
            ):
                raise SystemExit("unsafe archive member: " + member.name)
        # All members are regular files or directories; no link traversal.
        archive.extractall(
            destination,
            members=members,
            **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}),
        )
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise SystemExit("expected one archive root directory")
    return roots[0]


with tempfile.TemporaryDirectory(prefix="mica-release-") as temp:
    work = Path(temp)
    binary = extract(a.binary, work / "binary")
    tools = binary / "bin"
    for flag in ["--help", "--version"]:
        run([sys.executable, tools / "mica-cc", flag], work)
    for name in [
        "mica-as",
        "mica-ld",
        "mica-dis",
        "mica-run",
        "mica-nm",
        "mica-objdump",
        "mica-objcopy",
    ]:
        for flag in ["--help", "--version"]:
            run([tools / name, flag], work)
    for width in [32, 64]:
        main, helper = work / f"main{width}.mica", work / f"helper{width}.mica"
        main.write_text(
            f".arch mica{width}\n.global _start\n.extern helper\n_start: call helper\nwfi\n"
        )
        helper.write_text(
            f".arch mica{width}\n.global helper\nhelper: li8 x1,40\naddi x1,2\nret\n"
        )
        for source in [main, helper]:
            run(
                [
                    tools / "mica-as",
                    "--xlen",
                    width,
                    "-c",
                    source,
                    "-o",
                    source.with_suffix(".o"),
                ],
                work,
            )
        image = work / f"linked{width}"
        run(
            [
                tools / "mica-ld",
                main.with_suffix(".o"),
                helper.with_suffix(".o"),
                "-o",
                image.with_suffix(".bin"),
                "--elf",
                image.with_suffix(".elf"),
            ],
            work,
        )
        result = run(
            [tools / "mica-run", "--xlen", width, image.with_suffix(".elf")], work
        )
        if "x1=0x2a" not in result.stderr:
            raise SystemExit("installed linked SDK result mismatch")
        run([tools / "mica-dis", "--xlen", width, image.with_suffix(".elf")], work)
        run([tools / "mica-objdump", image.with_suffix(".elf")], work)
        run([tools / "mica-nm", image.with_suffix(".elf")], work)
        copy = image.with_suffix(".hex")
        run(
            [tools / "mica-objcopy", "-O", "ihex", image.with_suffix(".elf"), copy],
            work,
        )
        if not copy.read_text().endswith(":00000001FF\n"):
            raise SystemExit("installed HEX conversion failed")
        # Exercise the current ISA through installed tools, not just legacy ELF.
        parts = {
            "counted_main": ".global _start\n.extern helper\n_start: li8 x1,0\n"
            "li8 x2,7\n.global loop\nloop: addi x1,6\nb helper\n",
            "counted_helper": ".global helper\n.extern loop,payload\n"
            "helper: dbnz.s x2,loop\nadrpc x3,payload\n"
            "ldbu x4,[x3]\nadd x1,x4\nstop\n",
            "counted_data": ".align 256\n.global payload\npayload: .byte 0\n",
        }
        objects = []
        for name, code in parts.items():
            source = work / f"{name}{width}.mica"
            obj = source.with_suffix(".o")
            source.write_text(code)
            run(
                [
                    tools / "mica-as",
                    "--mica2",
                    "--xlen",
                    width,
                    "-c",
                    source,
                    "-o",
                    obj,
                ],
                work,
            )
            objects.append(obj)
        elf = work / f"counted{width}.elf"
        run(
            [
                tools / "mica-ld",
                *objects,
                "--elf",
                elf,
                "-o",
                work / f"counted{width}.bin",
            ],
            work,
        )
        result = run([tools / "mica-run", "--mica2", "--xlen", width, elf], work)
        if "x1=0x2a" not in result.stderr or "x3=0x100" not in result.stderr:
            raise SystemExit(
                "installed MICA 2.0 compact branch/address/alignment failed"
            )
        listing = run([tools / "mica-dis", "--assembly", elf], work).stdout
        if f".arch mica{width}v2" not in listing or "dbnz.s" not in listing:
            raise SystemExit("installed MICA 2.0 disassembly failed")
    sdk = binary / "share/mica"
    objects = []
    for source in [
        sdk / "runtime/startup/ram_start32.mica",
        sdk / "firmware/examples/multifile_main.mica",
        sdk / "runtime/startup/library32.mica",
    ]:
        obj = work / (source.stem + ".o")
        run([tools / "mica-as", "-c", source, "-o", obj], work)
        objects.append(obj)
    run(
        [
            tools / "mica-ld",
            *objects,
            "-T",
            sdk / "runtime/startup/ram.ld",
            "-o",
            work / "runtime.bin",
            "--elf",
            work / "runtime.elf",
        ],
        work,
    )
    result = run([tools / "mica-run", "--memory", "65536", work / "runtime.elf"], work)
    if result.stdout != "MICA linked CRC OK\n" or "x1=0x2a" not in result.stderr:
        raise SystemExit("installed runtime/startup/library failed")
    example = binary / "share/mica/examples/peripherals32.mica"
    run([tools / "mica-as", "--trap", example, "-o", work / "peripherals.bin"], work)
    result = run(
        [
            tools / "mica-run",
            "--trap",
            "--uart-input",
            "414243",
            work / "peripherals.bin",
        ],
        work,
    )
    if result.stdout != "ABC" or "x1=0x2a" not in result.stderr:
        raise SystemExit("installed peripheral firmware failed")
    if shutil.which("clang"):
        objects = []
        for name in ("sensor_node", "platform"):
            obj = work / (name + ".o")
            run(
                [
                    sys.executable,
                    tools / "mica-cc",
                    sdk / f"compiler/examples/{name}.c",
                    "--assembler",
                    tools / "mica-as",
                    "-o",
                    obj,
                ],
                work,
            )
            objects.append(obj)
        start = work / "sensor-start.o"
        run(
            [
                tools / "mica-as",
                "--profile",
                "MICA-2E",
                "-c",
                sdk / "firmware/examples/sensor_start32.mica",
                "-o",
                start,
            ],
            work,
        )
        elf = work / "sensor.elf"
        run(
            [
                tools / "mica-ld",
                start,
                *objects,
                "--elf",
                elf,
                "-o",
                work / "sensor.bin",
            ],
            work,
        )
        result = run(
            [
                tools / "mica-run",
                "--profile",
                "MICA-2E",
                "--watchdog",
                "--memory",
                65536,
                elf,
            ],
            work,
            raw=True,
        )
        if (
            result.stdout != bytes.fromhex("a500643ba5016529a502661fa503670d")
            or b"x1=0x2a" not in result.stderr
        ):
            raise SystemExit("installed compiled sensor failed")
    if a.source:
        source = extract(a.source, work / "source")
        # Check every source checksum without relying on platform sha256sum.
        import hashlib

        for line in (source / "SHA256SUMS").read_text().splitlines():
            expected, name = line.split("  ", 1)
            if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
                raise SystemExit("source checksum mismatch: " + name)
        build = work / "clean-build"
        run(["cmake", "-S", source, "-B", build, "-DCMAKE_BUILD_TYPE=Release"], work)
        run(["cmake", "--build", build, "--parallel", "4"], work)
        run(
            ["ctest", "--test-dir", build, "--output-on-failure", "--parallel", "4"],
            work,
        )
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(
    json.dumps(
        {
            "binary": str(a.binary),
            "source": str(a.source) if a.source else None,
            "passed": True,
            "commands": commands,
        },
        indent=2,
    )
    + "\n"
)
print(
    f"PASS extracted SDK tools, legacy and MICA 2.0 ELF for both XLENs, peripherals"
    + (", source checksums and clean build/CTest" if a.source else "")
)
