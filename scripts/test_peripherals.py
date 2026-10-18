#!/usr/bin/env python3
"""Test useful Verilog/VHDL blocks and GHDL's supported converted-netlist flow."""

import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument(
    "--assembler",
    type=Path,
    help="override the assembler executable (paths with spaces supported)",
)
p.add_argument("--tools", type=Path, default=ROOT / "build")
p.add_argument("--output", type=Path, default=ROOT / "build/peripherals")
a = p.parse_args()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=True)


def run(command, cwd=ROOT):
    result = subprocess.run(
        [str(x) for x in command], cwd=cwd, capture_output=True, text=True, timeout=60
    )
    with (out / "commands.log").open("a") as f:
        f.write(repr([str(x) for x in command]) + "\n" + result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    return result.stdout


(out / "commands.log").write_text("")
for name in ["mica_sync_fifo", "mica_uart_rx"]:
    binary = out / name
    run(
        [
            "iverilog",
            "-g2005",
            "-s",
            "tb_" + name,
            "-o",
            binary,
            ROOT / f"rtl/verilog/{name}.v",
            ROOT / f"rtl/verilog/tb_{name}.v",
        ]
    )
    print(run(["vvp", binary], cwd=out).strip())
with tempfile.TemporaryDirectory(prefix="mica-vhdl-") as temp:
    run(
        [
            "ghdl",
            "-a",
            "--std=08",
            ROOT / "rtl/vhdl/mica_crc32.vhd",
            ROOT / "rtl/vhdl/tb_mica_crc32.vhd",
        ],
        cwd=temp,
    )
    run(["ghdl", "-e", "--std=08", "tb_mica_crc32"], cwd=temp)
    print(
        run(
            [
                "ghdl",
                "-r",
                "--std=08",
                "tb_mica_crc32",
                "--assert-level=error",
                "--vcd=" + str(out / "crc32.vcd"),
            ],
            cwd=temp,
        ).strip()
    )
netlist = out / "mica_crc32.v"
netlist.write_text(
    run(
        [
            "ghdl",
            "--synth",
            "--std=08",
            "--out=verilog",
            ROOT / "rtl/vhdl/mica_crc32.vhd",
            "-e",
            "mica_crc32",
        ]
    )
)
sources = [
    ROOT / ("rtl/" + name)
    for name in [
        "mica_core_txn.sv",
        "mica_soc.sv",
        "mica_uart_tx.sv",
        "mica_crc_mmio.sv",
        "verilog/mica_sram_txn.v",
        "verilog/mica_sync_fifo.v",
        "verilog/mica_uart_rx.v",
    ]
] + [netlist]
for width in [32, 64]:
    source = ROOT / "examples/peripherals32.mica"
    if width == 64:
        source = out / "peripherals64.mica"
        source.write_text(
            (ROOT / "examples/peripherals32.mica")
            .read_text()
            .replace(".arch mica32", ".arch mica64")
            .replace("li32 x2,0x80000001", "li64 x2,0x8000000000000001")
        )
    run(
        [
            a.assembler.resolve() if a.assembler else a.tools.resolve() / "mica-as",
            "--xlen",
            width,
            "--trap",
            source,
            "-o",
            out / f"program{width}.bin",
        ]
    )
    run(
        [
            "python3",
            ROOT / "toolchain/bin2mem8.py",
            out / f"program{width}.bin",
            out / f"program_peripherals.mem{width}",
            "--width",
            width,
            "--pad-bytes",
            "65536",
        ]
    )
    names = ["crc_mmio", "peripherals"] if width == 32 else ["peripherals"]
    for name in names:
        binary = out / (name + str(width))
        options = [f"-Ptb_peripherals.XLEN={width}"] if name == "peripherals" else []
        run(
            [
                "iverilog",
                "-g2012",
                "-I" + str(ROOT / "isa/generated"),
                "-s",
                "tb_" + name,
                *options,
                "-o",
                binary,
                *sources,
                ROOT / f"rtl/tb_{name}.sv",
            ]
        )
        print(run(["vvp", binary], cwd=out).strip())
run(
    [
        a.assembler.resolve() if a.assembler else a.tools.resolve() / "mica-as",
        "--trap",
        ROOT / "examples/selftest32.mica",
        "-o",
        out / "arty.bin",
    ]
)
run(
    [
        "python3",
        ROOT / "toolchain/bin2mem8.py",
        out / "arty.bin",
        out / "program_arty.mem32",
        "--width",
        "32",
        "--pad-bytes",
        "4096",
    ]
)
run(
    [
        "iverilog",
        "-g2012",
        "-I" + str(ROOT / "isa/generated"),
        "-s",
        "tb_arty",
        "-o",
        out / "arty",
        *sources,
        ROOT / "boards/arty_a7/mica_arty_a7.sv",
        ROOT / "rtl/tb_arty.sv",
    ]
)
print(run(["vvp", out / "arty"], cwd=out).strip())
run(
    [
        "verilator",
        "--lint-only",
        "-Wall",
        "-Wno-UNUSEDPARAM",
        "-Wno-PINCONNECTEMPTY",
        "-I" + str(ROOT / "isa/generated"),
        "--top-module",
        "mica_arty_a7",
        "-GCRC_ENABLE=1",
        *sources,
        ROOT / "boards/arty_a7/mica_arty_a7.sv",
    ]
)
print("PASS full SoC lint with CRC/RX enabled; logs and waveforms: " + str(out))
