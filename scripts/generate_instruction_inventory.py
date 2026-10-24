#!/usr/bin/env python3
"""Generate an instruction-by-instruction engineering inventory from ISA data."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = chr(96)
REGIONS = {
    "R": (
        "scalar decode / arithmetic / control",
        "two-operand arithmetic, copies and control",
    ),
    "I": (
        "immediate arithmetic / short branch",
        "small constants, increments and short conditions",
    ),
    "MEM": (
        "transactional LSU / lane selection",
        "scalar object, array and stack accesses",
    ),
    "ALU": (
        "arithmetic() / optional shared multiplier",
        "distinct destination or high-register arithmetic",
    ),
    "IMM": (
        "immediate decode / shared scalar operations",
        "address offsets, masks and constant shifts",
    ),
    "WIDE": (
        "literal composition / PC adder",
        "large constants, symbols and PC-relative addresses",
    ),
    "BR": ("comparison / PC-relative adder", "two-register conditional control"),
    "J": ("PC-relative adder / x6 link write", "calls and long unconditional control"),
    "W32": ("word arithmetic / sign extension", "32-bit arithmetic on XLEN64"),
    "MX": (
        "transactional LSU / extension",
        "64-bit memory and explicit narrow extensions",
    ),
    "FLOW": (
        "LSU plus second commit slot",
        "stream traversal with precise pointer advancement",
    ),
    "LOOP": ("scalar decrement / branch", "counted loops with longer reach"),
    "BITOPS": ("optional bit_arithmetic()", "bit scans, rotates, masks and min/max"),
    "SYS": ("CSR decode and commit", "capability discovery and trap/timer management"),
    "V": ("no RTL datapath", "software-only vector experiment"),
    "2C": (
        "stack address / scalar decrement / STOP",
        "small stack slots, counters and test termination",
    ),
}


def inventory():
    spec = json.loads((ROOT / "isa/encodings/mica2.json").read_text())
    compact = json.loads((ROOT / "isa/encodings/mica2-compact.json").read_text())
    patterns = json.loads((ROOT / "isa/generated/encoding_patterns.json").read_text())
    rows = []
    for group, entries in spec["groups"].items():
        if group == "CSRS":
            continue
        for instruction in entries:
            row = dict(instruction)
            row["group"] = group
            row["fields"] = spec["formats"][group]["fields"]
            if group == "FLOW" and instruction["op"] < 8:
                row[
                    "fields"
                ] += "; short: op8[13:6] data3[5:3] base3[2:0], implicit natural stride"
            if row["name"] == "b":
                row["fields"] = "op3[13:11] rel11[10:0]"
            rows.append(row)
    semantics = {
        "ldsp": "Read XLEN bits at old SP plus unsigned scaled slot; commit destination only on success.",
        "stsp": "Store old source at old SP plus unsigned scaled slot; no base update.",
        "dbnz.s": "D=D-1 modulo 2^XLEN; branch from PC+2 if the result is nonzero; D must not be x0. No hidden loop state.",
        "stop": "Terminal halt until reset; not a power-saving sleep instruction.",
    }
    for name, allocation in compact["opcodes"].items():
        rows.append(
            {
                "name": name,
                "group": "2C",
                "extension": "2C",
                "since": "2.0",
                "op": allocation,
                "fields": (
                    "op8[13:6] data3[5:3] slot3[2:0]"
                    if name in ("ldsp", "stsp")
                    else (
                        "op8=33+rel6[5:3] counter3[5:3] rel6[2:0]"
                        if name == "dbnz.s"
                        else "op8[13:6]=41 zero6[5:0]"
                    )
                ),
                "semantics": semantics[name],
            }
        )
    for row in rows:
        group = row["group"]
        software = row["extension"] in ("A", "V")
        row["encodings"] = [
            {
                key: pattern[key]
                for key in ("group", "length", "mask", "value", "requires", "since")
            }
            for pattern in patterns
            if pattern["name"] == row["name"]
        ]
        row["xlen"] = (
            [64] if group in ("W32", "MX") or row["name"].endswith(".q") else [32, 64]
        )
        region, use = REGIONS[group]
        row["hardware"] = (
            "Software only; no supported RTL configuration" if software else region
        )
        row["compiler_use"] = use
        row["marginal_area"] = (
            "Not isolated per instruction; shared-region synthesis is reported separately"
        )
        memory = (
            group in ("MEM", "MX", "FLOW")
            or row["name"] in ("ldsp", "stsp")
            or row["extension"] == "A"
        )
        row["minimum_retirement_cycles"] = None if software else 7 if memory else 5
        row["latency_assumptions"] = (
            "aligned instruction already buffered; request accepted immediately; synchronous response next cycle; no trap/IRQ"
        )
        row["faults"] = (
            "alignment/access faults; failed access does not commit destination/base; stores require fault-atomic fabric"
            if memory
            else (
                "odd target/instruction access fault; precise control transfer"
                if group in ("BR", "J", "LOOP")
                or row["name"] in ("jr", "jalr", "eret", "dbnz.s")
                else (
                    "invalid/unimplemented/read-only CSR accesses trap"
                    if group == "SYS"
                    else "integer results wrap; no arithmetic overflow trap"
                )
            )
        )
        row[
            "faults"
        ] += "; reserved fields, unavailable extensions/registers and invalid revision are illegal"
        row["status"] = "Software only" if software else "Experimental"
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = inventory()
    text = "# Instruction engineering inventory\n\n"
    text += "Generated from the encoding JSON and disjoint allocation patterns. This describes the ISA 2.0 compatibility baseline of MICA 3.0 development; it adds no opcode. Masks are allocation envelopes in logical parcel order, not complete legality constraints or host byte order. Marginal area and routed timing are unmeasured. Minimum cycles assume an instruction-buffer hit, immediate request acceptance and next-cycle synchronous data response; this is not WCET. Misses, cross-word instructions, stalls, faults and interrupts add cycles.\n\n"
    text += "All scalar entries remain experimental. Assembler selection syntax is separate from hardware: two-operand arithmetic retains its short form; three-operand arithmetic selects short only when registers permit it, otherwise existing ALU3. Explicit add3 and peers retain their long encoding. High-register mov expands to add-with-zero. li selects known small literals; li32/li64 retain explicit object forms. No encoding is deleted or renumbered.\n\n"
    for group in REGIONS:
        members = [row for row in rows if row["group"] == group]
        text += f"## {group}\n\n"
        text += "| Instruction | Extension / XLEN | Bytes / mask:value | Register and immediate fields | Behavior | Typical use | RTL region / area attribution | Minimum cycles | Faults |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        for row in members:
            encodings = "; ".join(
                f"{item['length']}:{CODE}{item['mask']:#x}:{item['value']:#x}{CODE}"
                for item in row["encodings"]
            )
            behavior = row["semantics"].replace("|", "&#124;")
            text += f"| {CODE}{row['name']}{CODE} | {row['extension']} / {','.join(map(str,row['xlen']))} | {encodings} | {CODE}{row['fields']}{CODE} | {behavior} | {row['compiler_use']} | {row['hardware']}; marginal area unmeasured | {row['minimum_retirement_cycles'] or 'No RTL'} | {row['faults']} |\n"
        text += "\n"
    text += "Encoding variants share operations rather than imply distinct execution units. ALU3 and short arithmetic differ in operand reach/destructive update; W32 preserves XLEN64 sign extension; signed and unsigned loads retain distinct results. Useful compatibility forms are retained. Multi-register stack operations, new MAC/packed instructions and alternative compact register mappings require separately measured acceptance before allocation.\n"
    documents = {
        "docs/architecture/INSTRUCTION_INVENTORY.md": text,
        "isa/generated/instruction_inventory.json": json.dumps(rows, indent=2) + "\n",
    }
    for name, data in documents.items():
        path = ROOT / name
        if args.check:
            if path.read_text() != data:
                raise SystemExit("stale instruction inventory: " + name)
        else:
            path.write_text(data)
    print(f"PASS {len(rows)} instruction inventory entries")


if __name__ == "__main__":
    main()
