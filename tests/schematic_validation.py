#!/usr/bin/env python3
"""Reject fabricated schematic references and incompatible architectural widths."""

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_v3_schematics import validate, validate_widths
from v3_sheets import sheets


class SchematicValidation(unittest.TestCase):
    def setUp(self):
        inventory = json.loads(
            (ROOT / "docs/hardware/schematics/v3/rtl-inventory.json").read_text()
        )
        self.designs = {
            key: {
                "top": data["module"],
                "module": {
                    "netnames": {
                        name: {"bits": list(range(width))}
                        for name, width in data["net_widths"].items()
                    }
                },
            }
            for key, data in inventory.items()
        }

    def test_published_widths_and_references(self):
        validate_widths(self.designs)
        for sheet in sheets():
            validate(sheet, self.designs)

    def test_missing_signal_rejected(self):
        page = copy.deepcopy(sheets()[0])
        page["edges"][0] = ("pc", "fetch", "imaginary_signal")
        with self.assertRaisesRegex(ValueError, "missing net"):
            validate(page, self.designs)

    def test_wrong_xlen_bus_rejected(self):
        self.designs["core_l64"]["module"]["netnames"]["pc"]["bits"] = list(range(48))
        with self.assertRaisesRegex(ValueError, "architectural width"):
            validate_widths(self.designs)

    def test_missing_module_and_endpoint_rejected(self):
        page = copy.deepcopy(sheets()[0])
        page["module"] = "imaginary_cpu"
        with self.assertRaisesRegex(ValueError, "unknown sheet module"):
            validate(page, self.designs)
        page = copy.deepcopy(sheets()[0])
        page["edges"][0] = ("imaginary_alu", "fetch", "pc")
        with self.assertRaisesRegex(ValueError, "endpoint"):
            validate(page, self.designs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
