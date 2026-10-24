"""Validate ISA allocations and derive disjoint instruction envelopes."""

import re

FEATURES = {"base", "X", "M", "F", "A", "V", "B", "T", "2C"}


def patterns(spec, compact, profiles):
    result = []
    for group, fmt in spec["formats"].items():
        if (
            ("class" in fmt) == ("major" in fmt)
            or (
                "class" in fmt
                and (not isinstance(fmt["class"], int) or not 0 <= fmt["class"] < 3)
            )
            or (
                "major" in fmt
                and (not isinstance(fmt["major"], int) or not 0 <= fmt["major"] < 16)
            )
        ):
            raise ValueError(f"invalid {group} class/major")
        size = 14 if "class" in fmt else 26
        fields, occupied = {}, 0
        for token in fmt["fields"].split():
            match = re.fullmatch(r"([a-z]+)(\d+)\[(\d+):(\d+)\]", token)
            if not match:
                raise ValueError(f"invalid {group} field: {token}")
            name, width, high, low = match.groups()
            width, high, low = map(int, (width, high, low))
            if width != high - low + 1 or low < 0 or high >= size or name in fields:
                raise ValueError(f"invalid {group} field width/range: {token}")
            mask = ((1 << width) - 1) << low
            if mask & occupied:
                raise ValueError(f"overlapping {group} fields")
            occupied |= mask
            fields[name] = {"width": width, "lsb": low, "mask": mask}
        if occupied != (1 << size) - 1 or "op" not in fields:
            raise ValueError(f"incomplete {group} fields")
        prefix_mask = 0xC000 if size == 14 else 0xFC000000
        prefix = fmt["class"] << 14 if size == 14 else (0x30 | fmt["major"]) << 26
        # A long envelope is {class2, major4, payload26}, independent of byte order.
        for row in spec["groups"][group]:
            op = row["op"]
            required = row.get("requires", [row["extension"]])
            if not isinstance(op, int) or not 0 <= op < (1 << fields["op"]["width"]):
                raise ValueError(f"{group}/{row['name']}: opcode out of range")
            if (
                row["extension"] not in FEATURES
                or not set(required) <= FEATURES
                or row["extension"] not in required
            ):
                raise ValueError(f"{group}/{row['name']}: unknown extension")
            since = row.get("since", "2.0" if row["extension"] == "2C" else "1.0")
            if since not in ("1.0", "2.0") or (since == "2.0" and "2C" not in required):
                raise ValueError(f"{group}/{row['name']}: invalid version dependencies")
            fixed = fields["op"]["mask"] | fields.get("zero", {}).get("mask", 0)
            result.append(
                {
                    "name": row["name"],
                    "group": group,
                    "length": 2 if size == 14 else 4,
                    "mask": prefix_mask | fixed,
                    "value": prefix | (op << fields["op"]["lsb"]),
                    "since": since,
                    "requires": required,
                    "fields": fields,
                }
            )
    for row in spec["groups"]["FLOW"]:
        op = row["op"]
        if op >= 8:
            continue
        result.append(
            {
                "name": row["name"],
                "group": "FLOW-short",
                "length": 2,
                "mask": 0xFFC0,
                "value": (23 + op) << 6,
                "since": "1.0",
                "requires": ["F"],
            }
        )
    for name, allocation in compact["opcodes"].items():
        for op in allocation if isinstance(allocation, list) else [allocation]:
            if not isinstance(op, int) or not 0 <= op < 256:
                raise ValueError(f"{name}: compact opcode out of range")
            result.append(
                {
                    "name": name,
                    "group": "2C-short",
                    "length": 2,
                    "mask": 0xFFC0,
                    "value": op << 6,
                    "since": "2.0",
                    "requires": ["2C"],
                }
            )
    for index, left in enumerate(result):
        for right in result[index + 1 :]:
            if left["length"] == right["length"] and not (
                (left["value"] ^ right["value"]) & left["mask"] & right["mask"]
            ):
                raise ValueError(f"encoding overlap: {left['name']} / {right['name']}")
    for name, profile in profiles.items():
        if (
            profile["xlen"] not in (32, 64)
            or profile["registers"] != (16 if "X" in profile["extensions"] else 8)
            or not set(profile["extensions"]) <= FEATURES
        ):
            raise ValueError(f"invalid profile: {name}")
    return result
