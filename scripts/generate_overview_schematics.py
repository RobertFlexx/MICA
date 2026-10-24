#!/usr/bin/env python3
"""Refresh every legacy drawing path and fingerprint all MICA 2.0 schematics."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "schematics"


def graph(title, nodes, edges):
    lines = [
        "digraph G {",
        'graph [rankdir=LR,labelloc=t,fontname="DejaVu Sans",fontsize=16,pad=0.3];',
        'node [shape=box,style="rounded,filled",fillcolor="#f1f5f9",color="#475569",fontname="DejaVu Sans",fontsize=11];',
        'edge [fontname="DejaVu Sans",fontsize=9,color="#334155"];',
        "label=" + json.dumps("MICA 2.0 | " + title) + ";",
    ]
    for name, label in nodes.items():
        lines.append(f"{name} [label={json.dumps(label)}];")
    for source, target, label in edges:
        lines.append(f"{source} -> {target} [label={json.dumps(label)}];")
    return "\n".join(lines) + "\n}\n"


def pages():
    aliases = {
        "01-core-datapath": "mica2/02-core-datapath",
        "02-encoding": "mica2/01-isa-encoding",
        "04-soc-bus": "current/soc-peripherals",
        "10-trap-control": "current/traps",
        "13-core-signal-wiring": "current/core-ports",
        "14-memory-contract": "current/memory",
        "core": "mica2/02-core-datapath",
    }
    drawings = {
        name: (OUT / (source + ".dot")).read_text() for name, source in aliases.items()
    }
    drawings["03-flow-execution"] = graph(
        "F memory operations with compact counted branches",
        {
            "decode": "DECODE: read old base/data\nF enabled; base != 0 and base != data\ncheck alignment and register IDs",
            "request": "DREQ / DWAIT\nd_req_valid/ready; d_rsp_valid/ready\naddress = old base",
            "commit": "COMMIT on successful response\nload destination + base update\nstore base update only",
            "fault": "Access fault: discard pending writes\nno base/destination update\nfailed store must have no side effect",
            "loop": "dbnz.s: 2-byte counter branch\ncounter -= 1; branch if nonzero\n-64..+62 bytes from PC+2",
        },
        [
            ("decode", "request", "legal"),
            ("request", "commit", "d_rsp_error=0"),
            ("request", "fault", "d_rsp_error=1"),
            ("commit", "loop", "next instruction"),
            ("loop", "decode", "taken"),
        ],
    )
    drawings["05-controller-fsm"] = graph(
        "transactional controller, MICA2=1",
        {
            "START": "START\ninterrupt/alignment boundary",
            "LOOKUP": "LOOKUP\n32-bit aligned fetch reuse",
            "IREQ": "IREQ\nhold instruction request",
            "IWAIT": "IWAIT\nawait instruction response",
            "PARCEL": "PARCEL\nselect lo/hi halfword",
            "DECODE": "DECODE\nvalidate, queue effects",
            "DREQ": "DREQ\nhold data request",
            "DWAIT": "DWAIT\nawait data response",
            "COMMIT": "COMMIT\nregister/CSR/PC writes, retirement",
            "SLEEP": "SLEEP\nno fetch/data requests or retirement",
            "STOP": "STOP\nterminal until reset",
        },
        [
            ("START", "LOOKUP", "next instruction"),
            ("LOOKUP", "PARCEL", "reuse hit"),
            ("LOOKUP", "IREQ", "miss"),
            ("IREQ", "IWAIT", "i_req_ready"),
            ("IWAIT", "PARCEL", "successful response"),
            ("PARCEL", "LOOKUP", "long instruction crosses word / FAST_FETCH=0"),
            ("PARCEL", "DECODE", "short, second parcel, or aligned long + FAST_FETCH"),
            ("DECODE", "DREQ", "memory"),
            ("DECODE", "COMMIT", "nonmemory"),
            ("DREQ", "DWAIT", "d_req_ready"),
            ("DWAIT", "COMMIT", "successful response"),
            ("COMMIT", "START", "continue"),
            ("COMMIT", "SLEEP", "q_wait: WFI"),
            ("COMMIT", "STOP", "q_stop: explicit STOP"),
            ("SLEEP", "START", "pending wake event"),
            ("SLEEP", "START", "enabled interrupt: direct trap entry -> TVEC"),
            ("DECODE", "START", "recoverable trap -> TVEC"),
            ("DWAIT", "START", "recoverable access fault -> TVEC"),
            ("DECODE", "STOP", "unrecoverable fault"),
        ],
    )
    xdc = (ROOT / "boards/arty_a7/arty_a7.xdc").read_text()
    pins = re.findall(r"PACKAGE_PIN\s+(\w+).*?\[get_ports\s+(.+?)\]\s*$", xdc, re.M)
    nodes = {
        "fpga": "Arty A7-100 / xc7a100tcsg324-1\n100 MHz requested clock, active-high BTN0\nasync assert / synchronous reset release\nMICA2 parameter defaults to 0"
    }
    edges = []
    for i, (pin, port) in enumerate(pins):
        port = port.strip("{}")
        nodes[f"p{i}"] = f"{port}: {pin}\nLVCMOS33"
        incoming = port in ["CLK100MHZ", "btn_reset", "uart_rxd"]
        edges.append(
            (f"p{i}" if incoming else "fpga", "fpga" if incoming else f"p{i}", port)
        )
    drawings["06-arty-wiring"] = graph(
        "Arty connections read from the checked XDC", nodes, edges
    )
    drawings["15-board-electrical-topology"] = drawings["06-arty-wiring"]
    drawings["board"] = drawings["06-arty-wiring"]
    drawings["states"] = drawings["05-controller-fsm"]
    drawings["07-scalable-roadmap"] = graph(
        "future multicore proposal; absent from current RTL",
        {
            "current": "Current: one multicycle core\nno MPU or multicore RTL",
            "cores": "Proposed pipelined cores + MPU",
            "bus": "Proposed shared-SRAM arbiter\nlatency, ordering and fairness contracts",
            "atomic": "Proposed reservations / coherency\nper-hart interrupt controller",
        },
        [
            ("current", "cores", "future work"),
            ("cores", "bus", "proposed requests"),
            ("bus", "atomic", "requires verification"),
        ],
    )
    drawings["08-power-domains"] = graph(
        "implemented activity controls and unmeasured power",
        {
            "sleep": "WFI -> SLEEP\nno new instruction/data requests\nclock and enabled counters continue",
            "fetch": "One aligned-word reuse buffer\nselective invalidation on overlapping stores\nfence.i / traps invalidate; redirects use tags",
            "optional": "Static parameter guards\nMUL / BITOPS / TRAP / PERF\nunused paths removed by synthesis",
            "rails": "No implemented power-rail domains\nno clock gating or DVFS\nwatts/joules require physical measurement",
        },
        [
            ("sleep", "rails", "activity change only"),
            ("fetch", "rails", "memory traffic only"),
            ("optional", "rails", "mapped resource cost"),
        ],
    )
    drawings["09-bit-unit"] = graph(
        "optional B execution through precise commit",
        {
            "decode": "Major 11, op[25:20]\ndst[19:16], a[15:12], b[11:8]\nreserved low bits zero",
            "guard": "BITOPS parameter / register guards\nunary b=0; valid opcode",
            "rf": "8 or 16 x XLEN register array\nx0 fixed zero",
            "alu": "CLZ / CTZ / POPCNT / REV8\nrotate / min / max / Boolean ops",
            "pending": "q_value1 / q_dst1 / q_w1\nCOMMIT or precise fault",
        },
        [
            ("decode", "guard", "validate"),
            ("rf", "alu", "operands"),
            ("guard", "alu", "legal"),
            ("alu", "pending", "XLEN result"),
            ("pending", "rf", "successful retirement"),
        ],
    )
    drawings["11-split-slice-proposal"] = graph(
        "standalone segmented-adder experiment",
        {
            "operands": "64-bit add/sub operands\nenable + narrow mode",
            "low": "Low 33-bit adder\ncarry to upper slice",
            "high": "Upper 32-bit adder\nisolate operands/carry when narrow",
            "result": "Merge full-width result\nnarrow result sign extends low 32",
            "scope": "rtl/mica_add64.sv only\nmain core still uses conventional ALU\nformal equivalence and activity experiments",
        },
        [
            ("operands", "low", "low operands"),
            ("operands", "high", "isolated high operands"),
            ("low", "high", "carry when wide"),
            ("low", "result", "low result"),
            ("high", "result", "high result"),
            ("result", "scope", "no whole-CPU power claim"),
        ],
    )
    drawings["12-validation-chain"] = graph(
        "reproducible verification and remaining physical work",
        {
            "isa": "ISA + frozen 1.0 fixtures\nMICA2 compatibility mode",
            "software": "Release build / CTest\nassembly examples / matched RISC-V byte counts",
            "rtl": "Icarus SoC simulations\nVerilator retirement comparison\nrandom stalls / faults / reset / wake",
            "formal": "SBY component checks\nadder, SRAM, bounded FIFO\nnot a whole-core proof",
            "synth": "Yosys xc7 mapping\nlegacy + all three 2.0 profiles\nresource counts",
            "physical": "Pending: Vivado place/route\nphysical board boot / Fmax / rail power\nmatched RISC-V hardware comparison",
        },
        [
            ("isa", "software", "build"),
            ("software", "rtl", "compare"),
            ("rtl", "formal", "component properties"),
            ("formal", "synth", "map"),
            ("synth", "physical", "requires board/tool measurements"),
        ],
    )
    drawings["16-emulator-architecture"] = graph(
        "SDK emulator execution paths",
        {
            "cli": "mica-run\n--profile MICA-2C/2E/2L or --mica2",
            "elf": "ET_EXEC ELF input: verify XLEN and extension flags\nMICA2 feature requires matching runtime revision\nraw binaries skip ELF metadata",
            "reference": "Reference interpreter\nMICA2 operations / traps / wake",
            "fast": "--fast: selected scalar fast paths\nfallback to reference step",
            "native": "--native-loops: specialized legacy loop\nfallback for unsupported operations",
            "state": "Shared registers, memory, PC, CSRs\nretirement trace / modeled instruction steps",
        },
        [
            ("cli", "elf", "ELF executable"),
            ("elf", "reference", "validated input"),
            ("cli", "reference", "raw binary"),
            ("cli", "fast", "optional"),
            ("cli", "native", "optional"),
            ("native", "fast", "fallback"),
            ("fast", "reference", "fallback"),
            ("reference", "state", "architectural state"),
        ],
    )
    return drawings


def fingerprint():
    assets = sorted(
        p
        for p in OUT.rglob("*")
        if p.suffix in [".dot", ".svg", ".png", ".pdf", ".json"]
        and p.name != "manifest.json"
    )
    inputs = sorted(
        {
            *ROOT.glob("rtl/**/*.sv"),
            *ROOT.glob("rtl/**/*.v"),
            *ROOT.glob("rtl/**/*.vhd"),
            *ROOT.glob("boards/arty_a7/*.sv"),
            *ROOT.glob("boards/arty_a7/*.xdc"),
            *ROOT.glob("isa/**/*.json"),
            *ROOT.glob("scripts/generate*schematic*.py"),
            ROOT / "scripts/generate_mica2_diagrams.py",
            ROOT / "sim/emulator.cpp",
        }
    )

    def hashes(paths):
        return {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
        }

    return (
        json.dumps(
            {
                "architecture": "MICA 2.0",
                "inputs": hashes(inputs),
                "artifacts": hashes(assets),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drawings = pages()
    with tempfile.TemporaryDirectory(prefix="mica-overview-") as temp:
        config = Path(temp) / "fonts.conf"
        config.write_text(
            f"<fontconfig><dir>/usr/share/fonts</dir><cachedir>{temp}/fonts</cachedir></fontconfig>"
        )
        env = os.environ.copy()
        env["FONTCONFIG_FILE"] = str(config)
        for name, content in drawings.items():
            target = OUT / (name + ".dot")
            if args.check:
                if not target.exists() or target.read_text() != content:
                    raise SystemExit("stale overview schematic: " + str(target))
            else:
                target.write_text(content)
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
    manifest = OUT / "manifest.json"
    content = fingerprint()
    if args.check:
        if not manifest.exists() or manifest.read_text() != content:
            raise SystemExit(
                "stale schematic inputs/previews; regenerate all three sets and the overview manifest"
            )
    else:
        manifest.write_text(content)
    print(
        f"PASS {len(drawings)} overview drawings and SHA-256 of every schematic input/preview"
    )


if __name__ == "__main__":
    main()
