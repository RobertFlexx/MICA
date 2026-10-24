#!/usr/bin/env python3
"""Simulate compiled sensor firmware, UART pins, interrupts and idle activity."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tools", type=Path, default=ROOT / "build")
parser.add_argument("--output", type=Path, default=ROOT / "build/sensor-demo")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)


def run(command):
    result = subprocess.run(
        [str(x) for x in command], cwd=out, capture_output=True, text=True, timeout=120
    )
    with (out / "commands.log").open("a") as log:
        log.write(
            repr([str(x) for x in command]) + "\n" + result.stdout + result.stderr
        )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


(out / "commands.log").write_text("")
print(
    run(
        [
            sys.executable,
            ROOT / "scripts/build_sensor_demo.py",
            "--tools",
            args.tools.resolve(),
            "--output",
            out,
        ]
    ).strip()
)
symbols = {
    line.split()[1]: int(line.split()[0], 16)
    for line in (out / "sensor-node.map").read_text().splitlines()
}
watchdog = out / "mica_watchdog.v"
watchdog.write_text(
    run(
        [
            "ghdl",
            "--synth",
            "--std=08",
            "--out=verilog",
            ROOT / "rtl/vhdl/mica_event_counter.vhd",
            ROOT / "rtl/vhdl/mica_watchdog.vhd",
            "-e",
            "mica_watchdog",
        ]
    )
)
sources = [
    ROOT / ("rtl/" + name)
    for name in (
        "mica_core_txn.sv",
        "mica_soc.sv",
        "mica_uart_tx.sv",
        "mica_crc_mmio.sv",
        "verilog/mica_sram_txn.v",
        "verilog/mica_sync_fifo.v",
        "verilog/mica_uart_rx.v",
        "verilog/mica_uart_tx_portable.v",
        "tb_sensor_node.sv",
    )
]
run(
    [
        "iverilog",
        "-g2012",
        "-I" + str(ROOT / "isa/generated"),
        "-s",
        "tb_sensor_node",
        f"-Ptb_sensor_node.COUNTER_ADDR={symbols['measurement_count']}",
        "-o",
        out / "sensor-sim",
        *sources,
        watchdog,
    ]
)
print(run(["vvp", out / "sensor-sim"]).strip())

# Count transitions only at timestamps wholly inside one state. Boundaries are
# excluded so wake/entry work cannot be attributed to a stable sleep interval.
groups = {
    "datapath": {
        "q_value1",
        "q_value2",
        "q_nextpc",
        "q_addr",
        "q_store",
        "response_data",
        "cache_data",
        "parcel_word",
        "lo",
        "hi",
        "trace_regs",
    },
    "counters": {"cycle_count", "timer_count", "instret"},
}
selected, values, sleep_id, clock_id = {}, {}, None, None
counts = {
    mode: {"datapath": 0, "counters": 0, "clocks": 0} for mode in ("active", "sleep")
}
changes, sleeping = [], False


def flush():
    global sleeping
    next_sleep = next(
        (value == 1 for name, value in changes if name == sleep_id), sleeping
    )
    if next_sleep == sleeping:
        bucket = counts["sleep" if sleeping else "active"]
        for name, new in changes:
            if new is not None and name in values:
                if name == clock_id and new == 1 and values[name] == 0:
                    bucket["clocks"] += 1
                if name in selected:
                    bucket[selected[name]] += (values[name] ^ new).bit_count()
    for name, new in changes:
        if new is not None:
            values[name] = new
    sleeping = next_sleep
    changes.clear()


with (out / "sensor-node.vcd").open() as stream:
    for line in stream:
        words = line.split()
        if words and words[0] == "$var":
            name, identifier = words[4], words[3]
            if name == "sleeping":
                sleep_id = identifier
            if name == "clk":
                clock_id = identifier
            for group, names in groups.items():
                if name in names:
                    selected[identifier] = group
        elif line.startswith("#"):
            flush()
        elif line.startswith("b"):
            data, identifier = words
            changes.append(
                (
                    identifier,
                    int(data[1:], 2) if not any(c in data for c in "xz") else None,
                )
            )
        elif line and line[0] in "01xz":
            changes.append(
                (line[1:].strip(), int(line[0]) if line[0] in "01" else None)
            )
flush()
if (
    not sleep_id
    or not clock_id
    or counts["sleep"]["clocks"] < 7500
    or counts["sleep"]["datapath"] != 0
):
    raise AssertionError("sleep activity evidence missing or datapath toggled")
report = json.loads((out / "results.json").read_text())
report.update(json.loads((out / "rtl-results.json").read_text()))
report["selected_signal_bit_transitions"] = counts
report["activity_limits"] = (
    "Selected RTL signals, stable-state timestamps only, no routing/glitches/capacitance. The clock and timer remain active. No watt, joule, battery-life or clock-gating claim."
)
(out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
print("PASS stable sleep datapath activity; clock/timer activity reported separately")
