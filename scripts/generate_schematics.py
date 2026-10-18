#!/usr/bin/env python3
"""Render engineering drawings and validate every internal label against Yosys."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--check", action="store_true")
a = p.parse_args()
OUT = ROOT / "schematics/current"
OUT.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="mica-draw-") as temp:
    stage = Path(temp)
    for path in [ROOT / "rtl/mica_core_txn.sv", ROOT / "isa/generated/mica_isa.svh"]:
        shutil.copyfile(path, stage / path.name)
    command = [
        "yosys",
        "-Q",
        "-p",
        "read_verilog -sv -I. mica_core_txn.sv; chparam -set MICA2 1 mica_core_txn; hierarchy -top mica_core_txn; proc; write_json net.json",
    ]
    r = subprocess.run(command, cwd=stage, capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise SystemExit(r.stdout + r.stderr)
    module = json.loads((stage / "net.json").read_text())["modules"]["mica_core_txn"]
    ports = {
        k: {"direction": v["direction"], "width": len(v["bits"])}
        for k, v in module["ports"].items()
    }
    nets = {k: len(v["bits"]) for k, v in module["netnames"].items()}
    documents = {"ports.json": json.dumps(ports, indent=2, sort_keys=True) + "\n"}
    dot = 'digraph ports {rankdir=LR;node[shape=box,fontname="monospace"];\ncore[label="MICA 2.0: mica_core_txn\\nMICA2=1, XLEN=32, XREG=0\\nclk_i rising edge / rst_ni active low"];\n'
    for i, (name, prop) in enumerate(ports.items()):
        dot += f'n{i}[label="{name}[{prop["width"]}]"];\n'
        dot += f"n{i}->core;\n" if prop["direction"] == "input" else f"core->n{i};\n"
    documents["core-ports.dot"] = dot + "}\n"
    drawings = {
        "datapath": [
            ("PC", "fetch", "pc"),
            ("fetch", "decode", "lo"),
            ("fetch", "decode", "hi"),
            ("registers", "ALU", "decode.av"),
            ("registers", "ALU", "decode.bv"),
            ("ALU", "pending", "value1"),
            ("decode", "pending", "dst1"),
            ("decode", "pending", "nextpc"),
            ("pending", "commit", "q_value1"),
            ("pending", "commit", "q_value2"),
            ("pending", "commit", "q_w1"),
            ("pending", "commit", "q_w2"),
            ("commit", "PC", "q_nextpc"),
            ("bus", "commit", "response_data"),
            ("commit", "registers", "q_dst1"),
            ("commit", "registers", "q_dst2"),
        ],
        "fetch": [
            ("PC", "address_mux", "pc"),
            ("address_mux", "tag_compare", "fetch_addr"),
            ("cache_register", "tag_compare", "cache_tag"),
            ("tag_compare", "fsm", "cache_valid"),
            ("bus", "word_register", "i_rsp_rdata"),
            ("word_register", "halfword_mux", "parcel_word"),
            ("halfword_mux", "decode", "lo"),
            ("halfword_mux", "decode", "hi"),
            ("fsm", "bus", "i_req_valid"),
            ("bus", "fsm", "i_req_ready"),
            ("bus", "fsm", "i_rsp_valid"),
            ("fsm", "bus", "i_rsp_ready"),
            ("fsm", "bus", "i_req_addr"),
            ("bus", "fsm", "i_rsp_error"),
        ],
        "memory": [
            ("decode", "request_registers", "addr"),
            ("decode", "request_registers", "store_data"),
            ("decode", "request_registers", "size_log"),
            ("request_registers", "lane_mux", "q_store"),
            ("request_registers", "lane_mux", "q_addr"),
            ("lane_mux", "bus", "d_req_wdata"),
            ("lane_mux", "bus", "d_req_wstrb"),
            ("request_registers", "bus", "d_req_addr"),
            ("fsm", "bus", "d_req_valid"),
            ("bus", "fsm", "d_req_ready"),
            ("bus", "load_mux", "d_rsp_rdata"),
            ("bus", "fsm", "d_rsp_error"),
            ("bus", "fsm", "d_rsp_valid"),
            ("fsm", "bus", "d_rsp_ready"),
            ("load_mux", "commit", "response_data"),
        ],
        "traps": [
            ("external", "pending_logic", "irq_i"),
            ("software_pending", "pending_logic", "ip_reg"),
            ("timer", "pending_logic", "timer_count"),
            ("comparator", "pending_logic", "timer_cmp"),
            ("pending_logic", "priority", "pending"),
            ("mask", "priority", "ie_reg"),
            ("status", "priority", "status_reg"),
            ("priority", "trap_entry", "state"),
            ("vector", "trap_entry", "tvec_reg"),
            ("PC", "trap_entry", "pc"),
            ("trap_entry", "saved_state", "epc_reg"),
            ("trap_entry", "saved_state", "cause_reg"),
            ("trap_entry", "saved_state", "tval_reg"),
            ("decode", "commit", "csr_value"),
            ("commit", "CSR_write_mux", "q_csr_value"),
            ("commit", "CSR_write_mux", "q_csr"),
        ],
    }
    for name, edges in drawings.items():
        text = f'digraph {name} {{rankdir=LR;label="MICA 2.0: mica_core_txn {name}: actual local nets, XLEN32, MICA2=1\\nAll sequential state uses clk_i; asynchronous active-low rst_ni";node[shape=box];\n'
        for source, target, signal in edges:
            if signal not in nets:
                raise SystemExit("diagram signal no longer exists: " + signal)
            text += f'{source}->{target}[label="{signal}[{nets[signal]}]"];\n'
        documents[name + ".dot"] = text + "}\n"
    fontconfig = stage / "fonts.conf"
    fontconfig.write_text(
        f"<fontconfig><dir>/usr/share/fonts</dir><dir>/Library/Fonts</dir><cachedir>{stage}/font-cache</cachedir></fontconfig>"
    )
    render_env = os.environ.copy()
    render_env["FONTCONFIG_FILE"] = str(fontconfig)
    for name, text in documents.items():
        target = OUT / name
        if a.check:
            if not target.exists() or target.read_text() != text:
                raise SystemExit("stale schematic: " + str(target))
        else:
            target.write_text(text)
            if target.suffix == ".dot":
                for fmt in ["svg", "png", "pdf"]:
                    subprocess.run(
                        [
                            "dot",
                            "-T" + fmt,
                            str(target),
                            "-o",
                            str(target.with_suffix("." + fmt)),
                        ],
                        check=True,
                        env=render_env,
                        capture_output=True,
                    )
print("PASS diagram signals and ports match elaborated RTL")
