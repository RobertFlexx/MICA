#!/usr/bin/env python3
"""End-to-end MICA ELF revision, feature, relocation and loader regressions."""

import argparse
from pathlib import Path
import subprocess
import tempfile
import unittest

CLI = argparse.ArgumentParser()
CLI.add_argument("--tools", type=Path, required=True)
ARGS, EXTRA = CLI.parse_known_args()
TOOLS = ARGS.tools.resolve()


class ElfRevision(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def command(self, name, *args, success=True, contains=None):
        result = subprocess.run(
            [str(TOOLS / name), *(str(arg) for arg in args)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        if contains is not None:
            self.assertIn(contains, result.stdout + result.stderr)
        return result

    def assemble(self, name, code, width, revision=True, *options):
        source = self.root / (name + ".mica")
        output = self.root / (name + ".o")
        source.write_text(code, encoding="utf-8")
        self.command(
            "mica-as",
            "-c",
            *(["--mica2"] if revision else []),
            "--xlen",
            width,
            *options,
            source,
            "-o",
            output,
        )
        return output

    def test_multifile_v2_32_and_64_end_to_end(self):
        for width in (32, 64):
            with self.subTest(width=width):
                start = self.assemble(
                    f"main{width}",
                    f".arch mica{width}v2\n.global _start\n.extern helper\n"
                    "_start: li8 x1,40\ncall helper\nstop\n",
                    width,
                )
                helper = self.assemble(
                    f"helper{width}",
                    f".arch mica{width}v2\n.global helper\n" "helper: addi x1,2\nret\n",
                    width,
                )
                expected_flags = 0x10000 | (width == 64)
                for obj in (start, helper):
                    flags = int.from_bytes(obj.read_bytes()[48:52], "little")
                    self.assertEqual(flags, expected_flags)
                    self.command("mica-objdump", obj, contains="ISA=2.0")
                image = self.root / f"linked{width}.bin"
                executable = self.root / f"linked{width}.elf"
                self.command("mica-ld", start, helper, "-o", image, "--elf", executable)
                self.assertEqual(
                    int.from_bytes(executable.read_bytes()[48:52], "little"),
                    expected_flags,
                )
                for execution in ((), ("--fast",), ("--native-loops",)):
                    self.command(
                        "mica-run",
                        "--mica2",
                        "--xlen",
                        width,
                        *execution,
                        executable,
                        contains="x1=0x2a",
                    )
                self.command(
                    "mica-run",
                    "--xlen",
                    width,
                    executable,
                    success=False,
                    contains="ELF ISA revision differs",
                )
                output = self.root / f"extracted{width}.bin"
                self.command("mica-objcopy", "-O", "binary", executable, output)
                self.assertEqual(image.read_bytes(), output.read_bytes())

    def test_published_pic_style_symbol_examples(self):
        root = Path(__file__).resolve().parents[1]
        for width in (32, 64):
            with self.subTest(width=width):
                objects = []
                for kind in ("main", "data"):
                    obj = self.root / f"example_{kind}{width}.o"
                    source = (
                        root / "firmware/examples" / f"mica2_pcrel_{kind}{width}.mica"
                    )
                    self.command(
                        "mica-as",
                        "--mica2",
                        "--xlen",
                        width,
                        "-c",
                        source,
                        "-o",
                        obj,
                    )
                    objects.append(obj)
                elf = self.root / f"example{width}.elf"
                self.command(
                    "mica-ld",
                    *objects,
                    "--base",
                    "0x1000",
                    "--elf",
                    elf,
                    "-o",
                    self.root / f"example{width}.bin",
                )
                self.command(
                    "mica-run",
                    "--mica2",
                    "--xlen",
                    width,
                    elf,
                    contains="x1=0x2a",
                )

    def test_mixed_isa_semantics_are_not_linkable(self):
        for width in (32, 64):
            old = self.assemble(
                f"old{width}",
                f".arch mica{width}\n.global _start\n_start: wfi\n",
                width,
                revision=False,
            )
            new = self.assemble(
                f"new{width}",
                f".arch mica{width}v2\n.global helper\nhelper: stop\n",
                width,
            )
            self.command(
                "mica-ld",
                old,
                new,
                "-o",
                self.root / "forbidden.bin",
                success=False,
                contains="cannot mix MICA 1.0 and 2.0",
            )
            self.command(
                "mica-ld",
                new,
                old,
                "-o",
                self.root / "forbidden.bin",
                success=False,
                contains="cannot mix MICA 1.0 and 2.0",
            )
            self.command(
                "mica-ld",
                old,
                "-o",
                self.root / "legacy.bin",
                "--elf",
                self.root / "legacy.elf",
            )
            self.command("mica-run", "--xlen", width, self.root / "legacy.elf")
            self.command(
                "mica-run",
                "--mica2",
                "--xlen",
                width,
                self.root / "legacy.elf",
                success=False,
                contains="ELF ISA revision differs",
            )

    def test_reject_reserved_and_unknown_feature_bits(self):
        clean = self.assemble(
            "clean",
            ".arch mica32v2\n.global _start\n_start: stop\n",
            32,
        ).read_bytes()
        for mask in (2, 0x20000, 0x80000000):
            with self.subTest(mask=hex(mask)):
                mutated = bytearray(clean)
                old = int.from_bytes(mutated[48:52], "little")
                mutated[48:52] = (old | mask).to_bytes(4, "little")
                name = self.root / f"bad_{mask:x}.o"
                name.write_bytes(mutated)
                self.command(
                    "mica-ld",
                    name,
                    "-o",
                    self.root / "bad.bin",
                    success=False,
                    contains="unknown MICA ELF flags",
                )
                self.command(
                    "mica-objdump",
                    name,
                    success=False,
                    contains="unknown MICA ELF flags",
                )

    def test_parser_rejects_trailing_operands_and_symbol_addends(self):
        for instruction in ("li8 x1,1,", "addi x1,1,  ", ".word 12,"):
            with self.subTest(instruction=instruction):
                source = self.root / "trailing.mica"
                source.write_text(instruction + "\n")
                self.command(
                    "mica-as",
                    source,
                    "-o",
                    self.root / "bad.bin",
                    success=False,
                    contains="empty trailing operand",
                )
        for expression, error in (
            ("target+other", "relocation addend must be absolute"),
            ("target+9223372036854775808", "relocation addend exceeds"),
            ("target-9223372036854775809", "relocation addend exceeds"),
        ):
            with self.subTest(expression=expression):
                source = self.root / "bad_expression.mica"
                source.write_text(
                    ".arch mica32v2\n.global _start\n"
                    f"_start: adrpc x1,{expression}\n"
                    "target: stop\nother: stop\n"
                )
                self.command(
                    "mica-as",
                    "--mica2",
                    "-c",
                    source,
                    "-o",
                    self.root / "bad.o",
                    success=False,
                    contains=error,
                )
        # Signed relocation addends at their representable boundaries remain valid.
        for expression in ("target+9223372036854775807", "target-9223372036854775808"):
            source = self.root / "boundary.mica"
            source.write_text(
                ".arch mica32v2\n.global _start\n"
                f"_start: adrpc x1,{expression}\nstop\n"
                "target: stop\n"
            )
            self.command(
                "mica-as",
                "--mica2",
                "-c",
                source,
                "-o",
                self.root / "boundary.o",
            )

    def test_adrpc_symbol_relocation_forward_and_backward(self):
        for width in (32, 64):
            with self.subTest(width=width):
                head = self.assemble(
                    f"pcrel_main{width}",
                    f".arch mica{width}v2\n.global _start\n.extern target\n"
                    "_start: adrpc x1,target\nstop\n",
                    width,
                )
                tail = self.assemble(
                    f"pcrel_target{width}",
                    f".arch mica{width}v2\n.global target\n" "target: stop\n",
                    width,
                )
                self.command("mica-objdump", head, contains="ADRPC16 target")
                elf = self.root / f"forward{width}.elf"
                self.command(
                    "mica-ld",
                    head,
                    tail,
                    "--base",
                    "0x1000",
                    "--elf",
                    elf,
                    "-o",
                    self.root / "forward.bin",
                )
                self.command(
                    "mica-run",
                    "--mica2",
                    "--xlen",
                    width,
                    elf,
                    contains="x1=0x1010",
                )
                backward = self.root / f"backward{width}.elf"
                self.command(
                    "mica-ld",
                    tail,
                    head,
                    "--base",
                    "0x1000",
                    "--elf",
                    backward,
                    "-o",
                    self.root / "backward.bin",
                )
                self.command(
                    "mica-run",
                    "--mica2",
                    "--xlen",
                    width,
                    backward,
                    contains="x1=0x1000",
                )

    def test_adrpc_alignment_range_and_template_validation(self):
        target = self.assemble(
            "target", ".arch mica32v2\n.global target\ntarget: stop\n", 32
        )
        for expression, message in (
            ("target+1", "out of range/alignment"),
            ("target+65536", "out of range/alignment"),
        ):
            with self.subTest(expression=expression):
                main = self.assemble(
                    "invalid_adrpc",
                    ".arch mica32v2\n.global _start\n.extern target\n"
                    f"_start: adrpc x1,{expression}\nstop\n",
                    32,
                )
                self.command(
                    "mica-ld",
                    main,
                    target,
                    "-o",
                    self.root / "bad.bin",
                    success=False,
                    contains=message,
                )
        # A relocation is only legal at the exact WIDE/ADRPC instruction.
        good = self.assemble(
            "template",
            ".arch mica32v2\n.global _start\n.extern target\n"
            "_start: adrpc x1,target\nstop\n",
            32,
        )
        mutated = bytearray(good.read_bytes())
        section_headers = int.from_bytes(mutated[40:48], "little")
        image_offset = int.from_bytes(
            mutated[section_headers + 64 + 24 : section_headers + 64 + 32], "little"
        )
        first_parcel = int.from_bytes(
            mutated[image_offset : image_offset + 2], "little"
        )
        mutated[image_offset : image_offset + 2] = (first_parcel ^ (1 << 10)).to_bytes(
            2, "little"
        )
        damaged = self.root / "template_bad.o"
        damaged.write_bytes(mutated)
        self.command(
            "mica-ld",
            damaged,
            target,
            "-o",
            self.root / "bad.bin",
            success=False,
            contains="ADRPC16 relocation instruction template mismatch",
        )

    def test_required_extensions_are_checked_with_revision(self):
        source = self.assemble(
            "flow",
            ".arch mica32v2\n.global _start\n_start: stop\n",
            32,
            True,
            "--flow",
        )
        self.assertEqual(int.from_bytes(source.read_bytes()[48:52], "little"), 0x10400)
        binary = self.root / "flow.elf"
        self.command("mica-ld", source, "--elf", binary, "-o", self.root / "flow.bin")
        self.command(
            "mica-run",
            "--mica2",
            binary,
            success=False,
            contains="ELF requires disabled extensions: F",
        )
        self.command("mica-run", "--mica2", "--flow", binary)


if __name__ == "__main__":
    unittest.main(argv=[__file__, *EXTRA], verbosity=2)
