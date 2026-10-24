#!/usr/bin/env python3
"""Map C/E/64 SoCs to Xilinx 7-series primitives; archive all tool output."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, default=ROOT / "build/synthesis")
p.add_argument("--tools", type=Path, default=ROOT / "build")
p.add_argument(
    "--profiles",
    nargs="+",
    default=[
        "MICA-C",
        "MICA-E",
        "MICA-64",
        "MICA-E-peripherals",
        "MICA-2C",
        "MICA-2E",
        "MICA-2L",
        "MICA-2E-peripherals",
        "MICA-2E-parity",
    ],
)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
profiles = json.loads((ROOT / "isa/profiles/profiles.json").read_text())["profiles"]
report = {}
for name in a.profiles:
    devices = name.endswith("peripherals")
    parity = name.endswith("-parity")
    profile = profiles[name.removesuffix("-peripherals").removesuffix("-parity")]
    with tempfile.TemporaryDirectory(prefix="mica-synth-") as temp:
        stage = Path(temp)
        for source in [
            ROOT / "rtl/mica_core_txn.sv",
            ROOT / "rtl/mica_soc.sv",
            ROOT / "rtl/mica_uart_tx.sv",
            ROOT / "rtl/verilog/mica_uart_tx_portable.v",
            ROOT / "rtl/verilog/mica_sram_txn.v",
            ROOT / "rtl/verilog/mica_sync_fifo.v",
            ROOT / "rtl/verilog/mica_uart_rx.v",
            ROOT / "rtl/mica_crc_mmio.sv",
            ROOT / "isa/generated/mica_isa.svh",
        ]:
            shutil.copyfile(source, stage / source.name)
        if devices:
            generated = subprocess.run(
                [
                    "ghdl",
                    "--synth",
                    "--std=08",
                    "--out=verilog",
                    ROOT / "rtl/vhdl/mica_crc32.vhd",
                    "-e",
                    "mica_crc32",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            (stage / "mica_crc32.v").write_text(generated.stdout)
            generated = subprocess.run(
                [
                    "ghdl",
                    "--synth",
                    "--std=08",
                    "--out=verilog",
                    ROOT / "rtl/vhdl/mica_event_counter.vhd",
                    ROOT / "rtl/vhdl/mica_watchdog.vhd",
                    "-e",
                    "mica_watchdog",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            (stage / "mica_watchdog.v").write_text(generated.stdout)
        width, ext = profile["xlen"], profile["extensions"]
        code = (
            ROOT
            / "examples/firmware"
            / ("arithmetic64.bin" if width == 64 else "arithmetic32.bin")
        ).read_bytes()
        code = code.ljust(4096, b"\0")
        (stage / "program.mem32").write_text(
            "".join(
                f"{int.from_bytes(code[i:i+4], 'little'):08x}\n"
                for i in range(0, len(code), 4)
            )
        )
        (stage / "program.mem64").write_text(
            "".join(
                f"{int.from_bytes(code[i:i+8], 'little'):016x}\n"
                for i in range(0, len(code), 8)
            )
        )
        perf = name not in ["MICA-C", "MICA-2C"]
        params = f'.XLEN({width}),.XREG({int(profile["registers"] == 16)}),.RAM_BYTES(4096),.PERF({int(perf)}),.INIT_FILE("program.mem{width}")'
        params += f",.UART_RX({int(devices)}),.CRC_ENABLE({int(devices)}),.WATCHDOG_ENABLE({int(devices)})"
        params += f",.MICA2({int('2C' in ext)})"
        params += f",.REG_PARITY({int(parity)})"
        params += "".join(
            f",.{key}({int(feature in ext)})"
            for key, feature in [
                ("MUL", "M"),
                ("FLOW", "F"),
                ("BITOPS", "B"),
                ("TRAP", "T"),
            ]
        )
        (stage / "top.sv").write_text(
            "module mica_synth_top(input clk_i,rst_ni,irq_i,uart_rx_i,output uart_tx_o,output [7:0] leds_o,output halted_o,fault_o);\n"
            + f"mica_soc #({params}) soc(.*);\nendmodule\n"
        )
        extra_source = "mica_crc32.v mica_watchdog.v " if devices else ""
        script = (
            "read_verilog -sv -I. mica_core_txn.sv mica_soc.sv mica_uart_tx.sv mica_uart_tx_portable.v mica_sram_txn.v mica_sync_fifo.v mica_uart_rx.v mica_crc_mmio.sv "
            + extra_source
            + "top.sv; hierarchy -top mica_synth_top; synth_xilinx -top mica_synth_top -family xc7; check -assert; tee -o stats.json stat -json"
        )
        r = subprocess.run(
            ["yosys", "-Q", "-p", script],
            cwd=stage,
            capture_output=True,
            text=True,
            timeout=180,
        )
        (a.output / (name + ".log")).write_text(r.stdout + r.stderr)
        if r.returncode:
            raise SystemExit(r.stdout[-4000:] + r.stderr)
        data = json.loads((stage / "stats.json").read_text())
        (a.output / (name + ".json")).write_text(json.dumps(data, indent=2) + "\n")
        report[name] = {
            "xlen": width,
            "registers": profile["registers"],
            "mica2": "2C" in ext,
            "ram_bytes": 4096,
            "perf": perf,
            "extensions": ext,
            "uart_rx": devices,
            "crc_vhdl": devices,
            "watchdog_vhdl": devices,
            "reg_parity": parity,
            "cells": data["design"]["num_cells_by_type"],
        }
        print("PASS mapped synthesis", name)
(a.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
