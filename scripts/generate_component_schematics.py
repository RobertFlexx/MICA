#!/usr/bin/env python3
"""Draw independently elaborated portable Verilog and converted VHDL interfaces."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "schematics/current"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
inventory = {}
with tempfile.TemporaryDirectory(prefix="mica-component-draw-") as temp:
    stage = Path(temp)
    config = stage / "fonts.conf"
    config.write_text(
        f"<fontconfig><dir>/usr/share/fonts</dir><cachedir>{stage}/fonts</cachedir></fontconfig>"
    )
    env = os.environ.copy()
    env["FONTCONFIG_FILE"] = str(config)
    for name in (
        "mica_spi_master",
        "mica_uart_tx_portable",
        "mica_event_counter",
        "mica_watchdog",
    ):
        if name in ("mica_event_counter", "mica_watchdog"):
            files = [ROOT / "rtl/vhdl/mica_event_counter.vhd"]
            if name == "mica_watchdog":
                files.append(ROOT / "rtl/vhdl/mica_watchdog.vhd")
            converted = subprocess.run(
                [
                    "ghdl",
                    "--synth",
                    "--std=08",
                    "--out=verilog",
                    *map(str, files),
                    "-e",
                    name,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            source = stage / (name + ".v")
            source.write_text(converted.stdout)
        else:
            source = stage / (name + ".v")
            shutil.copyfile(ROOT / f"rtl/verilog/{name}.v", source)
        subprocess.run(
            [
                "yosys",
                "-Q",
                "-p",
                f"read_verilog {source}; hierarchy -top {name}; proc; check -assert; write_json component.json",
            ],
            cwd=stage,
            capture_output=True,
            text=True,
            check=True,
        )
        ports = json.loads((stage / "component.json").read_text())["modules"][name][
            "ports"
        ]
        inventory[name] = {
            port: {"width": len(data["bits"]), "direction": data["direction"]}
            for port, data in ports.items()
        }
        text = f'digraph component {{rankdir=LR;node[shape=box,fontname="monospace"];core[label="{name}\\nclk_i rising edge; rst_ni asynchronous active low\\nDefault parameters; interface widths from elaboration"];\n'
        for index, (port, data) in enumerate(inventory[name].items()):
            text += f'n{index}[label="{port}[{data["width"]}]"];\n'
            text += (
                f"n{index}->core;\n"
                if data["direction"] == "input"
                else f"core->n{index};\n"
            )
        text += "}\n"
        target = OUT / (name + ".dot")
        if args.check:
            if target.read_text() != text:
                raise SystemExit("stale component diagram: " + name)
        else:
            target.write_text(text)
            for fmt in ("svg", "pdf"):
                subprocess.run(
                    ["dot", "-T" + fmt, target, "-o", target.with_suffix("." + fmt)],
                    env=env,
                    capture_output=True,
                    check=True,
                )
    target = OUT / "component-ports.json"
    text = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    if args.check:
        if target.read_text() != text:
            raise SystemExit("stale component port inventory")
    else:
        target.write_text(text)
print("PASS portable component interfaces and native VHDL synthesis")
