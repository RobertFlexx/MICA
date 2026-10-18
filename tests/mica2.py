#!/usr/bin/env python3
"""Test the 2.0 compact encoding through real tool binaries."""

import argparse
from pathlib import Path
import subprocess
import tempfile
import unittest

p = argparse.ArgumentParser()
p.add_argument("--tools", type=Path, required=True)
a = p.parse_args()
TOOLS = a.tools


class Compact(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)

    def command(self, name, *args, success=True):
        r = subprocess.run(
            [str(TOOLS / name), *map(str, args)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if success:
            self.assertEqual(r.returncode, 0, r.stderr)
        else:
            self.assertNotEqual(r.returncode, 0, r.stdout)
        return r

    def assemble(self, text, width=32, rev2=True):
        source = self.root / "test.mica"
        target = self.root / "test.bin"
        source.write_text(text)
        self.command(
            "mica-as",
            *(["--mica2"] if rev2 else []),
            "--xlen",
            width,
            source,
            "-o",
            target,
        )
        return target

    def test_32_and_64(self):
        for width in (32, 64):
            with self.subTest(width=width):
                source = (
                    Path(__file__).resolve().parents[1]
                    / f"examples/mica2_short{width}.mica"
                )
                image = self.root / f"out{width}.bin"
                self.command("mica-as", "--mica2", "--xlen", width, source, "-o", image)
                self.assertEqual(len(image.read_bytes()), 16)
                for engine in [[], ["--fast"], ["--native-loops"]]:
                    result = self.command(
                        "mica-run", "--mica2", *engine, "--xlen", width, image
                    )
                    self.assertIn("x1=0x1c", result.stderr)
                    self.assertIn("x2=0x0", result.stderr)
                listing = self.command(
                    "mica-dis", "--assembly", "--xlen", width, image
                ).stdout
                self.assertIn("dbnz.s x2", listing)
                self.assertIn("ldsp x1", listing)
                self.assertIn("stsp x1", listing)
                self.assertEqual(
                    self.assemble(listing, width).read_bytes(), image.read_bytes()
                )

    def test_adrpc(self):
        image = self.assemble(".arch mica32v2\nadrpc x1,2\nstop\n")
        self.assertIn("x1=0x4", self.command("mica-run", "--mica2", image).stderr)
        self.assertIn("adrpc", self.command("mica-dis", image).stdout)

    def test_64bit_word_canonicalization(self):
        source = ".arch mica64v2\nli32 x1,0xffffffff\nstw x1,[sp]\nldw x2,[sp]\nstop\n"
        image = self.assemble(source, 64)
        self.assertIn(
            "x2=0xffffffffffffffff",
            self.command("mica-run", "--mica2", "--xlen", 64, image).stderr,
        )
        old = self.assemble(
            ".arch mica64\nli32 x1,0xffffffff\nstw x1,[sp]\nldw x2,[sp]\nwfi\n",
            64,
            False,
        )
        self.assertIn(
            "x2=0xffffffff", self.command("mica-run", "--xlen", 64, old).stderr
        )

    def test_invalid(self):
        bad = [
            "dbnz.s x0,0",
            "ldsp x1,[x6]",
            "stsp x1,[sp+2]",
            "ldsp x1,[sp+32]",
            "dbnz.s x1,200",
        ]
        for code in bad:
            with self.subTest(code=code):
                src = self.root / "bad.mica"
                src.write_text(code + "\n")
                self.command(
                    "mica-as",
                    "--mica2",
                    src,
                    "-o",
                    self.root / "bad.bin",
                    success=False,
                )
        src = self.root / "legacy.mica"
        src.write_text("ldsp x1,[sp]\n")
        self.command("mica-as", src, "-o", self.root / "legacy.bin", success=False)

    def test_literal_relaxation(self):
        short = self.assemble("li32 x3,0xffffffff\nstop\n")
        self.assertEqual(short.stat().st_size, 4)
        self.assertIn(
            "x3=0xffffffff", self.command("mica-run", "--mica2", short).stderr
        )
        wider = self.assemble("li32 x3,30000\nstop\n")
        self.assertEqual(wider.stat().st_size, 6)
        largest = self.assemble("li32 x3,0x12345678\nstop\n")
        self.assertEqual(largest.stat().st_size, 10)

    def test_minimal_core_wfi_sleep(self):
        image = self.assemble(".arch mica32v2\nwfi\nli8 x1,42\nstop\n")
        for engine in [[], ["--fast"], ["--native-loops"]]:
            no_irq = self.command(
                "mica-run", "--mica2", *engine, "--steps", 20, image, success=False
            )
            self.assertIn("step limit exceeded", no_irq.stderr)
            awake = self.command(
                "mica-run", "--mica2", *engine, "--irq-at", 1, "--steps", 20, image
            )
            self.assertIn("x1=0x2a", awake.stderr)

    def test_masked_irq_still_wakes_wfi(self):
        for flags in ([], ["--trap"]):
            with self.subTest(flags=flags):
                image = self.assemble(".arch mica32v2\nwfi\nli8 x1,42\nstop\n")
                awake = self.command(
                    "mica-run", "--mica2", *flags, "--irq-at", 1, "--steps", 20, image
                )
                self.assertIn("x1=0x2a", awake.stderr)
        image = self.assemble(
            ".arch mica32v2\nli8 x1,1\ncsrw ip,x1\nwfi\nli8 x1,42\nstop\n"
        )
        awake = self.command("mica-run", "--mica2", "--trap", "--steps", 20, image)
        self.assertIn("x1=0x2a", awake.stderr)

    def test_wfi_sleep_and_timer_wakeup(self):
        text = """.arch mica32v2
li32 x1,handler
csrw tvec,x1
li8 x1,2
csrw ie,x1
li8 x1,1
csrw status,x1
li8 x1,32
csrw cmp_lo,x1
li8 x1,0
csrw cmp_hi,x1
wfi
li8 x1,17
li32 x2,0xffff0004
stw x0,[x2]
handler:
  li8 x3,-1
  csrw cmp_hi,x3
  eret
"""
        image = self.assemble(text)
        result = self.command("mica-run", "--mica2", "--trap", "--steps", 300, image)
        self.assertIn("x1=0x11", result.stderr)


unittest.main(argv=["mica2.py"], verbosity=2)
