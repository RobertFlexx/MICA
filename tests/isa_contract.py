#!/usr/bin/env python3
"""ISA/toolchain integration invariants that previously escaped green CI."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

PARSER = argparse.ArgumentParser()
PARSER.add_argument("--tools", type=Path, required=True)
ARGS, EXTRA = PARSER.parse_known_args()
TOOLS = ARGS.tools.resolve()


class IsaContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def command(self, tool, *args, ok=True):
        result = subprocess.run(
            [str(TOOLS / tool), *map(str, args)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def assemble(self, name, code, width=32, obj=False, legacy=False, *options):
        source = self.root / (name + ".mica")
        output = source.with_suffix(".o" if obj else ".bin")
        source.write_text(code)
        self.command(
            "mica-as",
            "--xlen",
            width,
            *([] if legacy else ["--mica2"]),
            *(["-c"] if obj else []),
            *options,
            source,
            "-o",
            output,
        )
        return output

    def link(self, *objects, base=0):
        elf, binary = self.root / "linked.elf", self.root / "linked.bin"
        self.command("mica-ld", *objects, "--base", base, "--elf", elf, "-o", binary)
        return elf, binary.read_bytes()

    def test_literal_relaxation_rejects_overflow_before_narrowing(self):
        source, output = self.root / "bad.mica", self.root / "bad.bin"
        for literal in (
            "0x100000000",
            "0x100000001",
            "0x100007fff",
            "0x1ffffffff",
            "-4294967296",
            "-4294967297",
        ):
            with self.subTest(literal=literal):
                source.write_text(f"li32 x1,{literal}\nstop\n")
                output.write_bytes(b"preserve previous output")
                result = self.command(
                    "mica-as", "--mica2", source, "-o", output, ok=False
                )
                self.assertIn("li32 out of", result.stderr)
                self.assertEqual(output.read_bytes(), b"preserve previous output")
        for value in (0, -1, -128, 127, -32768, 32767, -2147483648, 0xFFFFFFFF):
            image = self.assemble("valid", f"li32 x1,{value}\nstop\n")
            result = self.command("mica-run", "--mica2", image)
            self.assertIn(f"x1=0x{value & 0xffffffff:x}", result.stderr)

    def test_compact_local_loop_relocates_at_both_widths(self):
        for width in (32, 64):
            obj = self.assemble(
                "loop",
                ".global _start\n_start: li8 x1,0\n"
                "li8 x2,7\nloop: addi x1,6\ndbnz.s x2,loop\nstop\n",
                width,
                obj=True,
            )
            self.assertIn("PCREL6 loop", self.command("mica-objdump", obj).stdout)
            elf, image = self.link(obj, base=0x1000)
            self.assertEqual(len(image), 10)
            result = self.command("mica-run", "--mica2", "--xlen", width, elf)
            self.assertIn("x1=0x2a", result.stderr)
            self.assertIn("x2=0x0", result.stderr)

    def test_compact_cross_object_displacements_and_limits(self):
        for width in (32, 64):
            head = self.assemble(
                "head",
                ".global _start\n_start: li8 x2,2\n"
                "li8 x1,0\ndbnz.s x2,target\nstop\n",
                width,
                obj=True,
            )
            tail = self.assemble(
                "tail", ".global target\ntarget: li8 x1,42\nstop\n", width, obj=True
            )
            for objects in ((head, tail), (tail, head)):
                elf, _ = self.link(*objects, base=0x1000)
                self.assertIn(
                    "x1=0x2a",
                    self.command("mica-run", "--mica2", "--xlen", width, elf).stderr,
                )
            for distance in (-64, 62, -66, 64, 1):
                # Absolute definitions isolate the exact signed range from padding.
                obj = self.assemble(
                    "limit",
                    f".equ target,{0x1002 + distance}\n"
                    ".global _start\n.extern destination\n"
                    "_start: dbnz.s x3,destination\nstop\n",
                    width,
                    obj=True,
                )
                target = self.assemble(
                    "absolute",
                    f".equ destination,{0x1002 + distance}\n"
                    ".global destination\nstop\n",
                    width,
                    obj=True,
                )
                if distance in (-64, 62):
                    elf, image = self.link(obj, target, base=0x1000)
                    half = int.from_bytes(image[:2], "little")
                    encoded = (((half >> 6) - 33) << 3) | (half & 7)
                    self.assertEqual(encoded, (distance // 2) & 63)
                    self.assertEqual((half >> 3) & 7, 3)
                else:
                    result = self.command(
                        "mica-ld",
                        obj,
                        target,
                        "--base",
                        "0x1000",
                        "-o",
                        self.root / "bad.bin",
                        ok=False,
                    )
                    self.assertIn("out of range/alignment", result.stderr)

    def test_compact_relocation_template_and_revision_are_checked(self):
        obj = self.assemble(
            "template", ".global _start\n_start: dbnz.s x3,_start\nstop\n", obj=True
        )
        original = obj.read_bytes()
        shoff = int.from_bytes(original[40:48], "little")
        image_at = int.from_bytes(original[shoff + 88 : shoff + 96], "little")
        for encoding in (0, 33 << 6, (41 << 6) | (3 << 3), 0xC000):
            damaged = bytearray(original)
            damaged[image_at : image_at + 2] = encoding.to_bytes(2, "little")
            bad = self.root / "template_bad.o"
            bad.write_bytes(damaged)
            result = self.command("mica-ld", bad, "-o", self.root / "bad.bin", ok=False)
            self.assertIn(
                "PCREL6 relocation instruction template mismatch", result.stderr
            )
        damaged = bytearray(original)
        damaged[48:52] = bytes(4)
        bad.write_bytes(damaged)
        self.assertIn(
            "requires MICA2", self.command("mica-objdump", bad, ok=False).stderr
        )

    def test_object_alignment_survives_linking_and_nonzero_origins(self):
        for width in (32, 64):
            head = self.assemble(
                "head",
                ".global _start\n_start: adrpc x3,payload\n" "ldbu x1,[x3]\nstop\n",
                width,
                obj=True,
            )
            tail = self.assemble(
                "aligned",
                ".align 256\n.global payload\npayload: .byte 42\n",
                width,
                obj=True,
            )
            self.assertIn("alignment=0x100", self.command("mica-objdump", tail).stdout)
            for base in (0, 0x1010):
                elf, image = self.link(head, tail, base=base)
                result = self.command("mica-run", "--mica2", "--xlen", width, elf)
                self.assertIn("x1=0x2a", result.stderr)
                addr = int(re.search(r"x3=0x([0-9a-f]+)", result.stderr)[1], 16)
                self.assertEqual(addr % 256, 0)
                self.assertEqual(image[addr - base], 42)
            # No _start: the default entry follows any initial alignment padding.
            first = self.assemble(
                "first", ".align 256\nli8 x1,42\nstop\n", width, obj=True
            )
            elf, _ = self.link(first, base=0x1010)
            self.assertIn(
                "x1=0x2a",
                self.command("mica-run", "--mica2", "--xlen", width, elf).stderr,
            )
            script = self.root / "small.ld"
            script.write_text("ORIGIN = 0;\nLENGTH = 32;\n")
            self.assertIn(
                "alignment exceeds memory region",
                self.command(
                    "mica-ld",
                    head,
                    tail,
                    "-T",
                    script,
                    "-o",
                    self.root / "bad.bin",
                    ok=False,
                ).stderr,
            )

    def test_illegal_trap_values_do_not_depend_on_trace(self):
        for width in (32, 64):
            for instruction in (
                ".half 0x3fff",
                ".half 0xffff,0x1234",
                "csrr x1,255",
                "eret",
            ):
                image = self.assemble(
                    "trap",
                    "li32 x4,handler\ncsrw tvec,x4\n"
                    f"fault: {instruction}\nhandler: csrr x1,tval\n"
                    "csrr x2,epc\ncsrr x3,cause\nstop\n",
                    width,
                    False,
                    False,
                    "--trap",
                )
                trace = self.root / "trace.jsonl"
                baseline = self.command(
                    "mica-run",
                    "--mica2",
                    "--trap",
                    "--xlen",
                    width,
                    "--retire-trace",
                    trace,
                    image,
                ).stderr
                fault = next(
                    event
                    for event in map(json.loads, trace.read_text().splitlines())
                    if event["trap"]
                )
                self.assertIn(f'x1=0x{fault["insn"]:x}', baseline)
                self.assertIn(f'x2=0x{fault["pc"]:x}', baseline)
                self.assertIn("x3=0x2", baseline)
                for engine in ((), ("--fast",), ("--native-loops",)):
                    self.assertEqual(
                        baseline,
                        self.command(
                            "mica-run",
                            "--mica2",
                            "--trap",
                            "--xlen",
                            width,
                            *engine,
                            image,
                        ).stderr,
                    )

    def test_disassembler_uses_elf_revision_and_extensions(self):
        for width in (32, 64):
            obj = self.assemble("v2", ".global _start\n_start: stop\n", width, obj=True)
            elf, _ = self.link(obj)
            listing = self.command("mica-dis", "--assembly", elf).stdout
            self.assertIn(f".arch mica{width}v2", listing)
            self.assertIn("stop", listing)
            self.command("mica-dis", "--mica1", elf, ok=False)
            # An instruction needing a disabled extension remains raw data.
            obj = self.assemble(
                "no_mul", ".global _start\n_start: .half 0x451\nstop\n", width, obj=True
            )
            elf, _ = self.link(obj)
            self.assertIn(".half 0x451", self.command("mica-dis", elf).stdout)
            # Identical bytes in a legacy ELF are reserved, not new 2C instructions.
            obj = self.assemble(
                "v1",
                ".global _start\n_start: .half 0xa40\nwfi\n",
                width,
                obj=True,
                legacy=True,
            )
            elf, _ = self.link(obj)
            self.assertIn(".half 0xa40", self.command("mica-dis", elf).stdout)
            raw = self.root / "linked.bin"
            self.assertIn(
                ".half 0xa40", self.command("mica-dis", "--mica1", raw).stdout
            )


if __name__ == "__main__":
    unittest.main(argv=[__file__, *EXTRA], verbosity=2)
