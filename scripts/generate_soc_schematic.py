#!/usr/bin/env python3
"""Draw actual module-port connections in the RX/CRC-enabled XLEN32 SoC."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from schematic_pdf import normalize_pdf

os.environ["SOURCE_DATE_EPOCH"] = "0"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "schematics/current"
p = argparse.ArgumentParser()
p.add_argument("--check", action="store_true")
a = p.parse_args()
with tempfile.TemporaryDirectory(prefix="mica-soc-draw-") as temp:
    stage = Path(temp)
    for source in [
        "rtl/mica_core_txn.sv",
        "rtl/mica_soc.sv",
        "rtl/mica_uart_tx.sv",
        "rtl/verilog/mica_uart_tx_portable.v",
        "rtl/mica_crc_mmio.sv",
        "rtl/verilog/mica_sram_txn.v",
        "rtl/verilog/mica_uart_rx.v",
        "rtl/verilog/mica_sync_fifo.v",
        "isa/generated/mica_isa.svh",
    ]:
        shutil.copyfile(ROOT / source, stage / Path(source).name)
    netlist = subprocess.run(
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
    (stage / "mica_crc32.v").write_text(netlist.stdout)
    netlist = subprocess.run(
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
    (stage / "mica_watchdog.v").write_text(netlist.stdout)
    (stage / "program.mem32").write_text("00000000\n" * (65536 // 4))
    command = "read_verilog -sv -I. mica_core_txn.sv mica_soc.sv mica_uart_tx.sv mica_uart_tx_portable.v mica_crc_mmio.sv mica_sram_txn.v mica_uart_rx.v mica_sync_fifo.v mica_crc32.v mica_watchdog.v; chparam -set MICA2 1 -set UART_RX 1 -set CRC_ENABLE 1 -set WATCHDOG_ENABLE 1 -set REG_PARITY 1 -set TRAP 1 mica_soc; hierarchy -top mica_soc; proc; write_json soc.json"
    result = subprocess.run(
        ["yosys", "-Q", "-p", command],
        cwd=stage,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    soc = json.loads((stage / "soc.json").read_text())["modules"]["mica_soc"]
    selected = [
        "core",
        "ram",
        "uart",
        "receive.rx",
        "receive.fifo",
        "checksum.bridge",
        "checksum.engine",
        "safety.watchdog",
    ]
    names = {}
    for name, net in sorted(
        soc["netnames"].items(),
        key=lambda item: (item[0].startswith("$"), len(item[0]), item[0]),
    ):
        names.setdefault(tuple(net["bits"]), name)
    dot = [
        'digraph soc {rankdir=LR;node[shape=box,fontname="monospace"];',
        'label="MICA 2.0: mica_soc: MICA2=1, XLEN32, UART_RX=1, CRC_ENABLE=1, WATCHDOG_ENABLE=1, REG_PARITY=1, TRAP=1\\nRAM_BYTES=65536. All modules clk_i rising edge, rst_ni active low. SRAM reset sampled on clk_i.\\nNet boxes are actual Yosys nets; $ names identify SoC combinational expressions.";',
    ]
    net_nodes = {}
    inventory = {}
    for index, name in enumerate(selected):
        cell = soc["cells"][name]
        node = f"c{index}"
        # Parameterized cell names contain hashes; use the source module name.
        module = {
            "core": "mica_core_txn",
            "ram": "mica_sram_txn",
            "uart": "mica_uart_tx",
            "receive.rx": "mica_uart_rx",
            "receive.fifo": "mica_sync_fifo",
            "checksum.bridge": "mica_crc_mmio",
            "checksum.engine": "mica_crc32",
            "safety.watchdog": "mica_watchdog",
        }[name]
        dot.append(f'{node}[label="{name}\\n{module}"];')
        inventory[name] = {"module": module, "ports": {}}
        for port, bits in cell["connections"].items():
            if not bits:
                continue
            key = tuple(bits)
            signal = names.get(
                key, "constant " + "".join(str(bit) for bit in reversed(bits))
            )
            direction = cell["port_directions"][port]
            inventory[name]["ports"][port] = {
                "direction": direction,
                "width": len(bits),
                "net": signal,
            }
            if port in ["clk_i", "rst_ni"]:
                continue
            if key not in net_nodes:
                wire = f"n{len(net_nodes)}"
                net_nodes[key] = wire
                label = json.dumps(f"{signal}[{len(bits)}]")
                dot.append(f"{wire}[shape=ellipse,label={label}];")
            wire = net_nodes[key]
            start, end = (wire, node) if direction == "input" else (node, wire)
            dot.append(f'{start}->{end}[label="{port}[{len(bits)}]"];')
    documents = {
        "soc-peripherals.dot": "\n".join(dot) + "\n}\n",
        "soc-ports.json": json.dumps(inventory, indent=2, sort_keys=True) + "\n",
    }
    for name, content in documents.items():
        target = OUT / name
        if a.check:
            if not target.exists() or target.read_text() != content:
                raise SystemExit("stale SoC schematic: " + str(target))
        else:
            target.write_text(content)
            if target.suffix == ".dot":
                config = stage / "fonts.conf"
                config.write_text(
                    f"<fontconfig><dir>/usr/share/fonts</dir><dir>/Library/Fonts</dir><cachedir>{stage}/font-cache</cachedir></fontconfig>"
                )
                env = os.environ.copy()
                env["FONTCONFIG_FILE"] = str(config)
                for fmt in ["svg", "png", "pdf"]:
                    subprocess.run(
                        [
                            "dot",
                            "-T" + fmt,
                            target,
                            "-o",
                            target.with_suffix("." + fmt),
                        ],
                        env=env,
                        capture_output=True,
                        check=True,
                    )
                    if fmt == "pdf":
                        normalize_pdf(target.with_suffix(".pdf"))
print("PASS RX/CRC SoC drawings and actual module-port wiring")
