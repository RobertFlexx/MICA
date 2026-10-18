#!/usr/bin/env python3
"""Reject overlapping or incomplete machine-readable ISA allocations."""

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from isa_schema import patterns


class Schema(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT / "isa/encodings/mica2.json").read_text())
        self.compact = json.loads((ROOT / "isa/encodings/mica2-compact.json").read_text())
        self.profiles = json.loads((ROOT / "isa/profiles/profiles.json").read_text())["profiles"]

    def validate(self):
        return patterns(self.spec, self.compact, self.profiles)

    def test_current_allocations(self):
        self.assertGreater(len(self.validate()), 160)

    def test_duplicate_opcode(self):
        self.spec["groups"]["ALU"].append(copy.deepcopy(self.spec["groups"]["ALU"][0]))
        with self.assertRaisesRegex(ValueError, "encoding overlap"):
            self.validate()

    def test_compact_collision(self):
        self.compact["opcodes"]["stop"] = 22
        with self.assertRaisesRegex(ValueError, "encoding overlap"):
            self.validate()

    def test_overlapping_fields(self):
        self.spec["formats"]["ALU"]["fields"] = "op6[25:20] rd4[20:17] rest18[17:0]"
        with self.assertRaisesRegex(ValueError, "overlapping.*fields"):
            self.validate()

    def test_unknown_extension_and_revision(self):
        for field, value in (("extension", "unknown"), ("since", "3.0")):
            with self.subTest(field=field):
                row = self.spec["groups"]["ALU"][0]
                old = row.get(field)
                row[field] = value
                with self.assertRaises(ValueError):
                    self.validate()
                if old is None:
                    del row[field]
                else:
                    row[field] = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
