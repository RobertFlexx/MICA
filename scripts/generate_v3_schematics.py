#!/usr/bin/env python3
"""Generate the source-backed, numbered MICA 3.0 engineering sheet collection."""

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from schematic_pdf import normalize_pdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/hardware/schematics/v3"
sys.path.insert(0, str(ROOT / "schematics"))
from v3_sheets import sheets

CORE = "rtl/mica_core_txn.sv"
SOURCES = [
    CORE,
    "rtl/mica_soc.sv",
    "rtl/mica_uart_tx.sv",
    "rtl/mica_crc_mmio.sv",
    "rtl/verilog/mica_sram_txn.v",
    "rtl/verilog/mica_uart_tx_portable.v",
    "rtl/verilog/mica_uart_rx.v",
    "rtl/verilog/mica_sync_fifo.v",
    "boards/arty_a7/mica_arty_a7.sv",
    "isa/generated/mica_isa.svh",
]
VHDL = [
    "rtl/vhdl/mica_event_counter.vhd",
    "rtl/vhdl/mica_watchdog.vhd",
    "rtl/vhdl/mica_crc32.vhd",
]


def checked(command, cwd, env=None):
    result = subprocess.run(
        [str(x) for x in command],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode:
        raise RuntimeError(result.stdout[-5000:] + result.stderr[-5000:])
    return result.stdout


def elaborate(stage):
    for name in SOURCES:
        shutil.copyfile(ROOT / name, stage / Path(name).name)
    for module, files in (("mica_watchdog", VHDL[:2]), ("mica_crc32", VHDL[2:])):
        generated = checked(
            [
                "ghdl",
                "--synth",
                "--std=08",
                "--out=verilog",
                *[ROOT / name for name in files],
                "-e",
                module,
            ],
            stage,
        )
        (stage / (module + ".v")).write_text(generated)
    (stage / "program.mem32").write_text("00000000\n" * 16384)
    files = " ".join(Path(name).name for name in SOURCES if not name.endswith(".svh"))
    read = "read_verilog -sv -I. " + files + " mica_watchdog.v mica_crc32.v; "
    extended = "-set MICA2 1 -set XREG 1 -set MUL 1 -set FLOW 1 -set BITOPS 1 -set TRAP 1 -set REG_PARITY 1"
    configs = {
        "core": ("mica_core_txn", "-set XLEN 32 " + extended),
        "core_c32": ("mica_core_txn", "-set MICA2 1 -set XLEN 32"),
        "core_l64": ("mica_core_txn", "-set XLEN 64 " + extended),
        "soc": (
            "mica_soc",
            "-set WATCHDOG_ENABLE 1 -set CRC_ENABLE 1 -set UART_RX 1 " + extended,
        ),
        "board": (
            "mica_arty_a7",
            "-set MICA2 1 -set WATCHDOG_ENABLE 1 -set CRC_ENABLE 1 -set REG_PARITY 1",
        ),
    }
    designs = {}
    for key, (top, params) in configs.items():
        (stage / "program.mem32").write_text(
            "00000000\n" * (1024 if key == "board" else 16384)
        )
        script = (
            read
            + f"chparam {params} {top}; hierarchy -top {top}; proc; write_json {key}.json"
        )
        checked(["yosys", "-Q", "-p", script], stage)
        design = json.loads((stage / (key + ".json")).read_text())
        designs[key] = {
            "top": top,
            "parameters": params,
            "module": design["modules"][top],
            "modules": design["modules"],
        }
    return designs


def net(design, name):
    nets = design["module"]["netnames"]
    if name not in nets:
        raise ValueError(f"{design['top']}: schematic references missing net {name}")
    return nets[name]["bits"]


def validate_widths(designs):
    scalar = (
        "pc",
        "fetch_addr",
        "cache_tag",
        "read_a_data",
        "read_b_data",
        "multiply_a",
        "multiply_b",
        "multiply_product",
        "q_value1",
        "q_value2",
        "q_nextpc",
        "q_addr",
        "q_store",
        "writeback_value",
        "status_reg",
        "epc_reg",
        "cause_reg",
        "tval_reg",
        "tvec_reg",
        "i_req_addr",
        "d_req_addr",
        "d_req_wdata",
        "d_rsp_rdata",
    )
    fixed = {
        "lo": 16,
        "hi": 16,
        "p": 26,
        "major": 4,
        "ilen": 3,
        "state": 4,
        "cache_data": 32,
        "parcel_word": 32,
        "csr_id": 8,
        "q_csr": 8,
        "timer_count": 64,
        "timer_cmp": 64,
        "cycle_count": 64,
        "instret": 64,
    }
    for key, xlen, count in (
        ("core", 32, 16),
        ("core_c32", 32, 8),
        ("core_l64", 64, 16),
    ):
        design = designs[key]
        for name, width in {
            **dict.fromkeys(scalar, xlen),
            **fixed,
            "d_req_wstrb": xlen // 8,
            "trace_regs": 16 * xlen,
        }.items():
            if len(net(design, name)) != width:
                raise ValueError(
                    f"{key}: {name} violates the {width}-bit architectural width"
                )
        registers = [
            name
            for name in design["module"]["netnames"]
            if re.fullmatch(r"regs\[\d+\]", name)
        ]
        if len(registers) != count or any(
            len(net(design, name)) != xlen for name in registers
        ):
            raise ValueError(f"{key}: register storage does not match its profile")


def width_label(designs, sheet, name):
    width = len(net(designs[sheet["module"]], name))
    alternate = (
        len(net(designs["core_l64"], name)) if sheet["module"] == "core" else width
    )
    dimensions = f"{width}/{alternate}" if alternate != width else str(width)
    return f"{name}[{dimensions}]", width


def validate(sheet, designs):
    if sheet["module"] not in designs:
        raise ValueError("unknown sheet module: " + sheet["module"])
    evidence = []
    for source, target, names in sheet["edges"]:
        if source not in sheet["nodes"] or target not in sheet["nodes"]:
            raise ValueError("missing functional-region endpoint")
        for name in names.split():
            _, width = width_label(designs, sheet, name)
            evidence.append({"net": name, "width": width, "from": source, "to": target})
    text = (ROOT / CORE).read_text()
    for anchor in sheet["anchors"]:
        if not re.search(r"\b" + re.escape(anchor) + r"\b", text):
            raise ValueError("missing RTL source anchor: " + anchor)
    return evidence


def quoted(text):
    return json.dumps(text)


def block(text):
    return "\n".join(
        "\n".join(
            textwrap.wrap(line, 34, break_long_words=False, break_on_hyphens=False)
        )
        for line in text.splitlines()
    )


def graph_start(sheet, release, digest):
    title = f"MICA {release['sdk_version']} development | {sheet['number']:02d} / 20 | {sheet['title']}"
    lines = [
        "digraph sheet {",
        'graph[rankdir=TB,bgcolor="white",fontname="DejaVu Sans",pad=0.35,nodesep=0.65,ranksep=0.9,splines=polyline,outputorder=edgesfirst,size="16.54,11.69",ratio=compress];',
        'node[shape=box,style="rounded,filled,dashed",fillcolor="#edf3f8",color="#334e68",fontname="DejaVu Sans",fontsize=11,margin="0.16,0.13",penwidth=1.2];',
        'edge[color="#174a70",fontname="DejaVu Sans Mono",fontsize=9,arrowsize=0.65,penwidth=1.2];',
    ]
    notes = '<BR ALIGN="LEFT"/>'.join(
        html.escape(line)
        for note in sheet["notes"]
        for line in textwrap.wrap(note, 125)
    )
    context = (
        "E32: XLEN=32, XREG/MUL/FLOW/BITOPS/TRAP/REG_PARITY=1"
        if sheet["module"] == "core"
        else (
            "Enabled SoC interfaces"
            if sheet["module"] == "soc"
            else "Arty A7-100 board interface"
        )
    )
    legend = "Blue: data. Dashed gray: control/handshake. Red: fault. Repeated Nxx labels connect without a wire. Crossings do not join."
    label = (
        f'<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="7">'
        f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="19"><B>{html.escape(title)}</B></FONT></TD></TR>'
        f'<TR><TD ALIGN="LEFT">ISA 2.0 compatibility baseline | {html.escape(context)} | {html.escape(sheet["status"])}</TD></TR>'
        f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="10">RTL source set {digest[:16]} | internal clock: clk_i rising edge; reset: rst_ni active low</FONT></TD></TR>'
        f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="10">{notes}</FONT></TD></TR>'
        f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="9">{html.escape(legend)}</FONT></TD></TR></TABLE>'
    )
    lines.append("graph[labelloc=t,label=<" + label + ">];")
    return lines


def grid(lines, rows):
    lines.append('spacer[style=invis,width=0.1,height=0.5,label=""];')
    lines.append(f"spacer->{rows[0][0]}[style=invis,weight=100];")
    for row in rows:
        lines.append("{rank=same;" + ";".join(row) + ";}")
        for left, right in zip(row, row[1:]):
            lines.append(f"{left}->{right}[style=invis,weight=100];")
    for upper, lower in zip(rows, rows[1:]):
        lines.append(f"{upper[0]}->{lower[0]}[style=invis,weight=100];")


def functional_graph(sheet, designs, release, digest):
    lines = graph_start(sheet, release, digest)
    names = list(sheet["nodes"])
    local_ports = {name: [] for name in names}
    wires = []
    for index, (source, target, nets) in enumerate(sheet["edges"], 1):
        first, last = names.index(source), names.index(target)
        if abs(last - first) >= 4 or last < first - 1:
            label = f"N{index:02d}: " + ", ".join(
                width_label(designs, sheet, net)[0] for net in nets.split()
            )
            local_ports[source].append("OUT " + label)
            local_ports[target].append("IN " + label)
        else:
            wires.append((source, target, nets))
    for name, label in sheet["nodes"].items():
        style = (
            ',fillcolor="#fff3d6",color="#8a5b16"'
            if sheet["status"] == "implementation gap"
            else ""
        )
        body = label
        if local_ports[name]:
            body += "\n----------------------\n" + "\n".join(local_ports[name])
        lines.append(f"{name}[label={quoted(block(body))}{style}];")
    grid(lines, [names[index : index + 3] for index in range(0, len(names), 3)])
    for source, target, nets in wires:
        labels = [width_label(designs, sheet, name)[0] for name in nets.split()]
        control = any(
            token in name
            for name in nets.split()
            for token in ("ready", "valid", "_w1", "_w2", "enable", "invalidate")
        )
        fault = any(token in nets for token in ("error", "fault", "cause", "illegal"))
        color = "#a12d2d" if fault else "#536574" if control else "#174a70"
        style = "dashed" if control else "solid"
        label = "\n".join(labels)
        lines.append(
            f"{source}->{target}[label={quoted(label)},color={quoted(color)},style={quoted(style)},constraint=false];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def controller_graph(sheet, designs, release, digest):
    text = (ROOT / CORE).read_text()
    match = re.search(
        r"typedef enum logic \[3\s*:\s*0\]\s*\{(.*?)\}\s*state_t", text, re.S
    )
    if not match:
        raise ValueError("controller enum is not recognized")
    states = re.findall(r"\b[A-Z][A-Z0-9_]+\b", match[1])
    expected = [
        "START",
        "LOOKUP",
        "IREQ",
        "IWAIT",
        "PARCEL",
        "DECODE",
        "DREQ",
        "DWAIT",
        "COMMIT",
        "SLEEP",
        "STOP",
    ]
    if states != expected:
        raise ValueError("FSM changed: review every transition and enable")
    enable = {
        "START": "interrupt / PC alignment check",
        "LOOKUP": "cache tag and valid",
        "IREQ": "i_req_valid; hold address",
        "IWAIT": "i_rsp_ready; capture parcel_word",
        "PARCEL": "write lo / hi; length detection",
        "DECODE": "validate; capture q_* effects",
        "DREQ": "d_req_valid; held request",
        "DWAIT": "d_rsp_ready; capture response_data",
        "COMMIT": "GPR / CSR / PC / trace enables",
        "SLEEP": "no requests or retirement",
        "STOP": "halt_o; no progress until reset",
    }
    transitions = {
        "START": "enabled IRQ or odd PC: T\notherwise: LOOKUP",
        "LOOKUP": "valid matching tag: PARCEL\nmiss: IREQ",
        "IREQ": "ready: IWAIT\notherwise: hold",
        "IWAIT": "valid, good: PARCEL\nvalid, error: T\notherwise: hold",
        "PARCEL": "cross-word / slow long: LOOKUP\ncomplete / aligned fast: DECODE",
        "DECODE": "parity error: STOP; illegal: T\nmemory: DREQ; other: COMMIT",
        "DREQ": "ready: DWAIT\notherwise: hold",
        "DWAIT": "valid, good: COMMIT\nvalid, error: T\notherwise: hold",
        "COMMIT": "ecall: T; q_wait: SLEEP\nq_stop: STOP; normal: START",
        "SLEEP": "enabled IRQ: T\nother pending: START; else hold",
        "STOP": "hold until reset",
    }
    lines = graph_start(sheet, release, digest)
    for state in states:
        label = (
            state
            + "\n"
            + enable[state]
            + "\n----------------------\n"
            + transitions[state]
        )
        lines.append(f"{state}[label={quoted(label)}];")
    grid(
        lines,
        [
            ["START", "LOOKUP", "IREQ", "IWAIT"],
            ["SLEEP", "COMMIT", "DECODE", "PARCEL"],
            ["STOP", "DWAIT", "DREQ"],
        ],
    )
    edges = [
        ("START", "LOOKUP", "no enabled IRQ; PC aligned"),
        ("START", "START", "recoverable IRQ / alignment trap: TVEC"),
        ("LOOKUP", "PARCEL", "FETCH_REUSE and matching valid tag"),
        ("LOOKUP", "IREQ", "miss"),
        ("IREQ", "IREQ", "!i_req_ready"),
        ("IREQ", "IWAIT", "i_req_ready"),
        ("IWAIT", "IWAIT", "!i_rsp_valid"),
        ("IWAIT", "PARCEL", "response valid; no error"),
        ("IWAIT", "START", "recoverable instruction access fault"),
        ("PARCEL", "LOOKUP", "long crosses word / FAST_FETCH=0"),
        ("PARCEL", "DECODE", "short, second parcel, or aligned FAST_FETCH"),
        ("DECODE", "COMMIT", "legal nonmemory"),
        ("DECODE", "DREQ", "legal memory"),
        ("DECODE", "START", "recoverable synchronous fault"),
        ("DECODE", "STOP", "register parity error / unrecoverable fault"),
        ("DREQ", "DREQ", "!d_req_ready"),
        ("DREQ", "DWAIT", "d_req_ready"),
        ("DWAIT", "DWAIT", "!d_rsp_valid"),
        ("DWAIT", "COMMIT", "response valid; no error"),
        ("DWAIT", "START", "recoverable data fault"),
        ("COMMIT", "START", "normal commit / recoverable ecall"),
        ("COMMIT", "SLEEP", "q_wait"),
        ("COMMIT", "STOP", "q_stop / unrecoverable ecall"),
        ("SLEEP", "START", "enabled IRQ: direct trap; other pending: wake"),
        ("STOP", "STOP", "until reset"),
    ]
    main_path = {
        ("START", "LOOKUP"),
        ("LOOKUP", "IREQ"),
        ("IREQ", "IWAIT"),
        ("IWAIT", "PARCEL"),
        ("PARCEL", "DECODE"),
        ("DECODE", "COMMIT"),
        ("DECODE", "DREQ"),
        ("DREQ", "DWAIT"),
        ("DWAIT", "COMMIT"),
        ("COMMIT", "SLEEP"),
        ("COMMIT", "STOP"),
    }
    for source, target, label in edges:
        if (source, target) in main_path:
            lines.append(f"{source}->{target}[constraint=false];")
    lines.append(
        'reset[shape=ellipse,label="rst_ni=0"];reset->START[label="asynchronous reset"];'
    )
    lines.append(
        'fault[shape=note,label="T = trap_entry() task (not a state)\nRecoverable: set TVEC/EPC/cause/status; START\nUnrecoverable entry or invalid state: fault_o=1; STOP\nAll other transitions and stalls are listed in state boxes.",fillcolor="#fdeaea"];'
    )
    lines.append("}")
    return "\n".join(lines) + "\n"


def soc_graph(sheet, designs, release, digest):
    soc = designs["soc"]["module"]
    selected = {
        "core": "mica_core_txn",
        "ram": "mica_sram_txn",
        "uart": "mica_uart_tx",
        "receive.rx": "mica_uart_rx",
        "receive.fifo": "mica_sync_fifo",
        "checksum.bridge": "mica_crc_mmio",
        "checksum.engine": "mica_crc32",
        "safety.watchdog": "mica_watchdog",
    }
    lines = graph_start(sheet, release, digest)
    lines.append(
        'fabric[label="mica_soc parent nets and logic\nRepeated labels are the same elaborated net.\nNxxx labels identify anonymous generated nets;\nexact bit IDs and RTL names are in soc-connectivity.json.",fillcolor="#e3edf2"];'
    )
    inventory = {}
    net_names = {}
    for name, data in sorted(
        soc["netnames"].items(),
        key=lambda item: (item[0].startswith("$"), len(item[0]), item[0]),
    ):
        net_names.setdefault(tuple(data["bits"]), name)
    anonymous = {}
    for index, (instance, module) in enumerate(selected.items()):
        cell = soc["cells"][instance]
        if module not in cell["type"]:
            raise ValueError("instance module mismatch: " + instance)
        node = "c" + str(index)
        inventory[instance] = {"module": module, "ports": {}}
        groups = {"input": [], "output": []}
        for port, bits in cell["connections"].items():
            direction = cell["port_directions"][port]
            key = tuple(bits)
            actual = net_names.get(key)
            if actual and not actual.startswith("$"):
                display = actual
            elif all(isinstance(bit, str) for bit in bits):
                display = f"{len(bits)}'b" + "".join(reversed(bits))
            else:
                anonymous.setdefault(key, f"N{len(anonymous)+1:03d}")
                display = anonymous[key]
            inventory[instance]["ports"][port] = {
                "direction": direction,
                "width": len(bits),
                "bits": bits,
                "net": actual,
                "label": display,
            }
            if (
                port in ("clk_i", "rst_ni")
                or not bits
                or port.startswith("trace_")
                or port in ("pc_o", "debug_a0_o")
            ):
                continue
            groups[direction].append(f"{port}[{len(bits)}] : {display}")
        cells = [
            f'<TR><TD COLSPAN="2"><B>{html.escape(instance)}</B><BR/>{module}</TD></TR>',
            "<TR><TD><B>IN</B></TD><TD><B>OUT</B></TD></TR>",
        ]
        height = max(len(groups["input"]), len(groups["output"]))
        for row in range(height):
            values = [
                groups[direction][row] if row < len(groups[direction]) else ""
                for direction in ("input", "output")
            ]
            cells.append(
                "<TR>"
                + "".join(
                    f'<TD ALIGN="LEFT">{html.escape(value)}</TD>' for value in values
                )
                + "</TR>"
            )
        label = (
            '<TABLE BORDER="0" CELLBORDER="0" CELLPADDING="3">'
            + "".join(cells)
            + "</TABLE>"
        )
        lines.append(f'{node}[label=<{label}>,fontsize=10,style="rounded,filled"];')
    grid(lines, [["c0", "c1"], ["fabric"], ["c2", "c3", "c4"], ["c5", "c6", "c7"]])
    lines.append("}")
    return "\n".join(lines) + "\n", inventory


def board_graph(sheet, designs, release, digest):
    reference = json.loads((ROOT / "boards/arty_a7/pin_reference.json").read_text())
    xdc = (ROOT / "boards/arty_a7/arty_a7.xdc").read_text()
    pins = {
        port.strip("{}"): pin
        for pin, port in re.findall(
            r"PACKAGE_PIN\s+(\w+).*?\[get_ports\s+(.+?)\]\s*$", xdc, re.M
        )
    }
    if pins != reference["pins"]:
        raise ValueError("board constraints differ from the verified vendor pin map")
    ports = designs["board"]["module"]["ports"]
    lines = graph_start(sheet, release, digest)
    lines.append(
        'board[label="mica_arty_a7\nxc7a100tcsg324-1\n4 KiB SRAM / onboard USB-UART\nReset release synchronizer",fillcolor="#e3edf2"];'
    )
    for index, (port, pin) in enumerate(pins.items()):
        base = port.split("[")[0]
        if base not in ports:
            raise ValueError("constraint references a missing board port")
        if "[" in port and int(port.split("[")[1][:-1]) >= len(ports[base]["bits"]):
            raise ValueError("board bus index out of range")
        label = f"{port}\nPackage pin {pin} / LVCMOS33"
        lines.append(f"p{index}[shape=component,label={quoted(label)}];")
        left, right = (
            (f"p{index}", "board")
            if ports[base]["direction"] == "input"
            else ("board", f"p{index}")
        )
        lines.append(f'{left}->{right}[label="1 bit"];')
    lines.append("}")
    return "\n".join(lines) + "\n", reference


def main():
    os.environ["SOURCE_DATE_EPOCH"] = "0"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    release = json.loads((ROOT / "release.json").read_text())
    inputs = sorted(
        {
            *SOURCES,
            *VHDL,
            "boards/arty_a7/arty_a7.xdc",
            "boards/arty_a7/pin_reference.json",
            "release.json",
            "schematics/v3_sheets.py",
            "scripts/generate_v3_schematics.py",
            "scripts/schematic_pdf.py",
        }
    )
    fingerprints = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs
    }
    digest = hashlib.sha256(
        json.dumps(fingerprints, sort_keys=True).encode()
    ).hexdigest()
    collection = sheets()
    if [sheet["number"] for sheet in collection] != list(range(1, 21)):
        raise ValueError("the collection must contain exactly sheets 01 through 20")
    documents, validation = {}, {"source_sha256": fingerprints, "sheets": []}
    with tempfile.TemporaryDirectory(prefix="mica-v3-draw-") as temp:
        stage = Path(temp)
        designs = elaborate(stage)
        validate_widths(designs)
        for sheet in collection:
            evidence = validate(sheet, designs)
            if sheet["number"] == 10:
                drawing = controller_graph(sheet, designs, release, digest)
            elif sheet["number"] == 17:
                drawing, ports = soc_graph(sheet, designs, release, digest)
                documents["soc-connectivity.json"] = (
                    json.dumps(ports, indent=2, sort_keys=True) + "\n"
                )
            elif sheet["number"] == 18:
                drawing, pins = board_graph(sheet, designs, release, digest)
                documents["board-pins.json"] = (
                    json.dumps(pins, indent=2, sort_keys=True) + "\n"
                )
            else:
                drawing = functional_graph(sheet, designs, release, digest)
            stem = f"{sheet['number']:02d}-{sheet['slug']}"
            documents[stem + ".dot"] = drawing
            validation["sheets"].append(
                {
                    "number": sheet["number"],
                    "title": sheet["title"],
                    "status": sheet["status"],
                    "rtl_module": designs[sheet["module"]]["top"],
                    "validated_nets": evidence,
                    "notes": sheet["notes"],
                }
            )
        inventories = {
            key: {
                "module": design["top"],
                "parameters": design["parameters"],
                "ports": {
                    name: {"direction": data["direction"], "width": len(data["bits"])}
                    for name, data in design["module"]["ports"].items()
                },
                "net_widths": {
                    name: len(data["bits"])
                    for name, data in design["module"]["netnames"].items()
                    if not name.startswith("$")
                },
            }
            for key, design in designs.items()
        }
        documents["rtl-inventory.json"] = (
            json.dumps(inventories, indent=2, sort_keys=True) + "\n"
        )
        documents["validation.json"] = (
            json.dumps(validation, indent=2, sort_keys=True) + "\n"
        )
        index = "# MICA 3.0 development engineering sheets\n\n"
        index += "This new collection documents implemented ISA 2.0-compatible hardware. It is an RTL engineering reference, not a physical electrical schematic. Pipeline/security gaps are status sheets; unsupported circuitry is not drawn. Internal boxes are named functional regions of the monolithic core. Sheet 17 records actual instance ports and elaborated connection bits.\n\n"
        index += "Generate with `python3 scripts/generate_v3_schematics.py`; CI uses `--check`. Net names, widths, module instances, board pins, source hashes and committed previews are checked. Internal region arrows describe RTL signal flow; they are not a gate-level connectivity proof.\n\n"
        index += "| Sheet | Topic | Editable source | SVG | PDF | PNG |\n| --- | --- | --- | --- | --- | --- |\n"
        for sheet in collection:
            stem = f"{sheet['number']:02d}-{sheet['slug']}"
            index += f"| {sheet['number']:02d} | {sheet['title']} | [DOT]({stem}.dot) | [SVG]({stem}.svg) | [PDF]({stem}.pdf) | [PNG]({stem}.png) |\n"
        index += "\n[Validation](validation.json), [RTL widths and ports](rtl-inventory.json), [SoC connection bits](soc-connectivity.json), [verified board map](board-pins.json).\n\n"
        index += "C32, E32 and L64 cores are elaborated independently; displayed core pages use E32 and annotate differing L64 widths. The SoC view enables RX/CRC/watchdog/parity. The real board wrapper retains its actual smaller scalar configuration. No routed timing, physical energy or qualification is implied.\n"
        documents["README.md"] = index
        fontconfig = stage / "fonts.conf"
        fontconfig.write_text(
            f"<fontconfig><dir>/usr/share/fonts</dir><dir>/Library/Fonts</dir><cachedir>{stage}/fonts</cachedir></fontconfig>"
        )
        env = os.environ.copy()
        env["FONTCONFIG_FILE"] = str(fontconfig)
        for name, text in documents.items():
            target = out / name
            if args.check:
                if not target.exists() or target.read_text() != text:
                    raise SystemExit("stale v3 schematic: " + name)
            else:
                target.write_text(text)
                if target.suffix == ".dot":
                    for fmt in ("svg", "pdf", "png"):
                        checked(
                            [
                                "dot",
                                "-T" + fmt,
                                "-Gdpi=120",
                                target,
                                "-o",
                                target.with_suffix("." + fmt),
                            ],
                            stage,
                            env,
                        )
                        if fmt == "pdf":
                            normalize_pdf(target.with_suffix(".pdf"))
        artifacts = {}
        for name in documents:
            path = out / name
            candidates = (
                [path, *[path.with_suffix("." + fmt) for fmt in ("svg", "pdf", "png")]]
                if path.suffix == ".dot"
                else [path]
            )
            for item in candidates:
                if not item.exists() or item.stat().st_size == 0:
                    raise SystemExit("missing v3 schematic artifact: " + item.name)
                artifacts[item.name] = hashlib.sha256(item.read_bytes()).hexdigest()
        manifest = (
            json.dumps(
                {"inputs": fingerprints, "artifacts": artifacts},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        target = out / "manifest.json"
        if args.check:
            if target.read_text() != manifest:
                raise SystemExit("stale v3 previews or manifest")
        else:
            target.write_text(manifest)
    print(
        "PASS 20 new engineering sheets, five elaborated configurations, signal widths, instance ports and board pins"
    )


if __name__ == "__main__":
    main()
