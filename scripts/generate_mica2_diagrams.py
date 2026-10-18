#!/usr/bin/env python3
"""Generate MICA 2.0 wiring diagrams. Keep labels tied to real RTL signals."""

from pathlib import Path
import argparse
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
rtl = (root / "rtl/mica_core_txn.sv").read_text()
soc = (root / "rtl/mica_soc.sv").read_text()
board = (root / "boards/arty_a7/mica_arty_a7.sv").read_text()
required_core = [
    "i_req_valid",
    "i_req_ready",
    "i_req_addr",
    "i_rsp_valid",
    "i_rsp_ready",
    "i_rsp_rdata",
    "d_req_valid",
    "d_req_ready",
    "d_req_addr",
    "d_req_wdata",
    "d_req_wstrb",
    "d_rsp_valid",
    "d_rsp_ready",
    "d_rsp_rdata",
    "pc",
    "lo",
    "hi",
    "q_w1",
    "q_value1",
    "q_value2",
    "q_nextpc",
    "q_mem",
    "q_addr",
    "status_reg",
    "epc_reg",
    "timer_count",
    "timer_cmp",
    "pending",
    "cache_data",
    "regs",
    "trace_retired",
    "SLEEP",
    "MICA2",
]
for signal in required_core:
    if signal not in rtl:
        raise SystemExit("missing RTL symbol: " + signal)
for signal in [
    "mica_core_txn",
    "mica_sram_txn",
    "mica_uart_tx",
    "uart_tx_o",
    "leds_o",
    "crc_select",
    "ram_select",
]:
    if signal not in soc:
        raise SystemExit("missing SoC symbol: " + signal)
for signal in ["CLK100MHZ", "btn_reset", "uart_rxd", "uart_txd", "led", "MICA2"]:
    if signal not in board:
        raise SystemExit("missing Arty port: " + signal)

head = """digraph G {
  graph [fontname="DejaVu Sans", fontsize=16, labelloc=t, rankdir=LR, bgcolor="white", pad=0.30, nodesep=0.55, ranksep=1.0, splines=polyline, compound=true];
  node [shape=box, style="rounded,filled", fillcolor="#f1f5f9", color="#475569", fontname="DejaVu Sans", fontsize=11, margin="0.18,0.12"];
  edge [fontname="DejaVu Sans", fontsize=9, color="#334155", arrowsize=0.7];
"""


def node(k, label, fill="#f1f5f9"):
    label = label.replace("\\", "\\\\").replace('"', '\\"')
    return f'  {k} [label="{label}", fillcolor="{fill}"];\n'


def edge(a, b, label="", style="solid"):
    label = label.replace('"', '\\"')
    return f'  {a} -> {b} [label="{label}",style="{style}"];\n'


pages = {}
s = head + ' label="MICA 2.0 | compact encodings and shared execution hardware";\n'
s += node(
    "r",
    "R class, 16 bits\n[15:14]=00, [13:6]=op8\n[5:3]=data/counter, [2:0]=slot/offset",
    "#dbeafe",
)
s += node("legacy", "MICA 1.0\nR opcodes 0..22, 23..30 F\nRemains decodable", "#e2e8f0")
s += node(
    "ldsp",
    "op=31: ldsp\nEA = old SP + slot * XLEN/8\nload XLEN, write data register",
    "#dcfce7",
)
s += node(
    "stsp",
    "op=32: stsp\nEA = old SP + slot * XLEN/8\nstore XLEN, SP unchanged",
    "#dcfce7",
)
s += node(
    "dbnz",
    "op=33..40: dbnz.s\n6-bit signed halfword displacement\nreg <- reg-1; branch if nonzero\n-64..+62 byte reach",
    "#dcfce7",
)
s += node(
    "stop",
    "op=41: stop\nExplicit terminal debug halt\nWFI remains wakeable sleep",
    "#fee2e2",
)
s += node(
    "wide", "WIDE major 2, op=3\nadrpc d,disp16\nd = PC + (sext(disp16) * 2)", "#fff3cd"
)
s += node(
    "gate",
    "MICA2 parameter / feature bit 8\nIllegal on 1.0 cores\nNo second ALU or register bank",
    "#fef2f2",
)
for a, b, l in [
    ("r", "legacy", "existing"),
    ("r", "ldsp", "2.0"),
    ("r", "stsp", "2.0"),
    ("r", "dbnz", "2.0"),
    ("r", "stop", "2.0"),
    ("r", "gate", "feature"),
    ("gate", "wide", "enable"),
]:
    s += edge(a, b, l)
pages["01-isa-encoding"] = s + "}\n"

s = head + ' label="MICA 2.0 | transactional scalar datapath with register commit";\n'
for k, l, c in [
    ("fetch", "Fetch cache\ncache_data[31:0]\ni_req_*, i_rsp_*", "#dbeafe"),
    ("parcel", "Halfword select\nlo[15:0], hi[15:0]", "#dbeafe"),
    ("decode", "Decode\nclass, major, op\n8 or 16 GPR IDs", "#e2e8f0"),
    ("registers", "Register file\n8 or 16 x XLEN\nx0 always zero, x7 SP", "#dcfce7"),
    ("alu", "Shared integer ALU\nXLEN bits\nadd, sub, shift, branch", "#fef3c7"),
    ("address", "Address generation\nSP + slot * XLEN/8", "#fef3c7"),
    (
        "request",
        "Transactional LSU\nd_req_addr[XLEN]\nd_req_wstrb[XLEN/8]\nd_rsp_rdata[XLEN]",
        "#fae8ff",
    ),
    (
        "pending",
        "Pending result registers\nq_value1, q_value2\nq_w1, q_w2, q_nextpc",
        "#dcfce7",
    ),
    ("retire", "Commit + retirement\nregs write, PC update\ntrace_retired", "#dcfce7"),
    ("trap", "Trap control\nstatus_reg, epc_reg\npending, SLEEP", "#fee2e2"),
]:
    s += node(k, l, c)
for a, b, l in [
    ("fetch", "parcel", "i_rsp_rdata[31:0]"),
    ("parcel", "decode", "lo,hi [16]"),
    ("decode", "registers", "index[4]"),
    ("registers", "alu", "av,bv [XLEN]"),
    ("registers", "address", "SP/data [XLEN]"),
    ("alu", "pending", "value1 [XLEN]"),
    ("address", "request", "q_addr [XLEN]"),
    ("request", "pending", "response_data [XLEN]"),
    ("decode", "pending", "dst1,dst2"),
    ("pending", "retire", "q_w1,q_w2,q_value1,q_value2"),
    ("retire", "registers", "2 logical writebacks"),
    ("retire", "fetch", "next PC [XLEN]"),
    ("trap", "retire", "exception controls"),
    ("request", "trap", "d_rsp_error"),
]:
    s += edge(a, b, l)
pages["02-core-datapath"] = s + "}\n"

s = head + ' label="MICA 2.0 | stack loads/stores and precise retirement";\n'
for k, l, c in [
    ("decode", "R opcode 31/32\nregister d[2:0], slot[2:0]", "#dbeafe"),
    ("read", "Read SP (x7) and d\nold architectural values", "#dcfce7"),
    (
        "ea",
        "EA = x7 + slot * XLEN/8\nXLEN=32: 0..28 bytes\nXLEN=64: 0..56 bytes",
        "#fef3c7",
    ),
    ("issue", "DREQ\nd_req_valid + d_req_addr\nwait for d_req_ready", "#f1f5f9"),
    ("wait", "DWAIT\nd_rsp_valid + d_rsp_ready\nbackpressure stable", "#f1f5f9"),
    (
        "error",
        "Access fault\nno register writeback\nstore error: memory unchanged",
        "#fee2e2",
    ),
    (
        "commit",
        "COMMIT\nldsp: write d = loaded XLEN\nstsp: no GPR write\nSP remains unchanged",
        "#dcfce7",
    ),
]:
    s += node(k, l, c)
for a, b, l in [
    ("decode", "read", "d,slot"),
    ("read", "ea", "SP+index"),
    ("ea", "issue", "q_addr"),
    ("issue", "wait", "accepted request"),
    ("wait", "error", "d_rsp_error=1"),
    ("wait", "commit", "d_rsp_error=0"),
]:
    s += edge(a, b, l)
pages["03-stack-and-memory"] = s + "}\n"

s = head + ' label="MICA 2.0 | wakeable WFI and terminal STOP";\n'
for k, l, c in [
    ("start", "START\ncheck interrupts, alignment", "#dbeafe"),
    ("commit", "COMMIT\nretire WFI, update PC\nq_wait set in MICA2", "#dcfce7"),
    ("sleep", "SLEEP\ni_req_valid=0\nd_req_valid=0\nno new retirement", "#fff3cd"),
    (
        "pending",
        "Wake detection\nexternal irq_i always\nwith T: software ip_reg\nand timer_count >= timer_cmp",
        "#f1f5f9",
    ),
    (
        "resume",
        "START after wake\ninterrupt trap only if T enabled,\nstatus_reg[0] and ie_reg mask",
        "#dcfce7",
    ),
    ("halt", "STOP on legacy WFI (MICA2=0)\nor 2.0 explicit stop", "#fee2e2"),
]:
    s += node(k, l, c)
for a, b, l in [
    ("start", "commit", "fetch/decode WFI"),
    ("commit", "sleep", "MICA2, with or without T"),
    ("commit", "halt", "legacy, no T"),
    ("sleep", "pending", "clock continues"),
    ("pending", "sleep", "no event"),
    ("pending", "resume", "pending != 0"),
    ("resume", "start", "next tick"),
]:
    s += edge(a, b, l)
pages["04-wfi-and-traps"] = s + "}\n"

s = head + ' label="MICA 2.0 | SoC wiring and board-level boundary";\n'
for k, l, c in [
    ("board", "Arty A7\nCLK100MHZ, btn_reset\nuart_rxd, uart_txd\nled[3:0]", "#dbeafe"),
    ("reset", "Reset synchronizer\nrst_release[1:0]\nrst_ni", "#f1f5f9"),
    ("soc", "mica_soc\nXLEN, RAM_BYTES\nMICA2 parameter (default 0)", "#dbeafe"),
    ("core", "mica_core_txn\ntransactional CPU", "#dcfce7"),
    ("memory", "mica_sram_txn\nshared code/data RAM\nsynchronous responses", "#fef3c7"),
    ("mux", "Address decode\nram_select / crc_select\nMMIO response mux", "#fef3c7"),
    ("uart", "mica_uart_tx\n115200 at 100 MHz", "#dcfce7"),
    ("rx", "Optional UART RX + FIFO\nRX interrupt source", "#dcfce7"),
    ("crc", "Optional CRC-32 bridge\nVHDL checksum.engine", "#dcfce7"),
    ("gpio", "GPIO + halt/fault LEDs\nleds_o[1:0], halted, fault", "#dcfce7"),
    (
        "watch",
        "SoC IRQ synchronizer\nirq_sync[1:0]\nArty external irq_i tied low",
        "#f1f5f9",
    ),
]:
    s += node(k, l, c)
for a, b, l in [
    ("board", "reset", "CLK100MHZ/btn_reset"),
    ("reset", "soc", "rst_ni; clock is direct"),
    ("soc", "core", "MICA2, XLEN"),
    ("core", "memory", "i_req/i_rsp"),
    ("core", "mux", "d_req/d_rsp"),
    ("mux", "memory", "RAM transaction"),
    ("mux", "uart", "uart_send,uart_byte"),
    ("mux", "gpio", "MMIO write"),
    ("uart", "board", "uart_txd"),
    ("board", "rx", "uart_rxd"),
    ("rx", "core", "receive_interrupt"),
    ("mux", "rx", "FIFO MMIO"),
    ("mux", "crc", "CRC MMIO"),
    ("gpio", "board", "led[3:0]"),
    ("watch", "core", "irq_sync[1]"),
]:
    s += edge(a, b, l)
pages["05-fpga-topology"] = s + "}\n"

s = head + ' label="MICA 2.0 | minimum and expanded implementation profiles";\n'
for k, l, c in [
    (
        "shared",
        "Shared architecture\n16/32-bit instruction decode\n32-bit fetch, XLEN-bit data bus\nTransactional retirement",
        "#dbeafe",
    ),
    (
        "c",
        "MICA-2C\nXLEN32, 8 GPR slots\nNo multiply or SIMD required\nMICA2 compact ops",
        "#dcfce7",
    ),
    (
        "e",
        "MICA-2E\nXLEN32, 16 GPR slots\nM, F, B, T, 2C\nLarger register bank, more registers",
        "#fff3cd",
    ),
    (
        "l",
        "MICA-2L\nXLEN64, 16 GPR slots\nM, F, B, T, 2C\nHigher hardware cost",
        "#fee2e2",
    ),
    (
        "metrics",
        "Measure per core, same flow\nLUTs, FFs, Fmax, memory traffic\njoules/workload after hardware test",
        "#f1f5f9",
    ),
]:
    s += node(k, l, c)
for a, b, l in [
    ("shared", "c", "smallest"),
    ("shared", "e", "compiler-friendly"),
    ("shared", "l", "optional 64-bit"),
    ("c", "metrics", "baseline"),
    ("e", "metrics", "tradeoff"),
    ("l", "metrics", "tradeoff"),
]:
    s += edge(a, b, l)
pages["06-profiles-and-cost"] = s + "}\n"

p = argparse.ArgumentParser()
p.add_argument("--check", action="store_true")
args = p.parse_args()
out = root / "schematics/mica2"
out.mkdir(parents=True, exist_ok=True)
if not shutil.which("dot"):
    raise SystemExit("graphviz dot is needed for drawing previews")
for name, src in pages.items():
    dot = out / (name + ".dot")
    if args.check:
        if not dot.exists() or dot.read_text() != src:
            raise SystemExit("stale schematic: " + str(dot))
    else:
        dot.write_text(src)
    for fmt in ["svg", "png", "pdf"]:
        preview = out / (name + "." + fmt)
        if args.check:
            if not preview.exists():
                raise SystemExit("missing schematic preview: " + str(preview))
        else:
            subprocess.run(
                ["dot", "-T" + fmt, str(dot), "-o", str(preview)], check=True
            )
print(f"PASS: {len(pages)} drawings tied to MICA-2C core/SoC signal names")
