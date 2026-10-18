#!/usr/bin/env python3
"""Regression tests for the r2 fault contract, ELF tools and untrusted inputs."""

import argparse
import json
from pathlib import Path
import random
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = None


class Engineering(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def command(self, tool, *args, ok=True):
        p = subprocess.run(
            [str(TOOLS / tool), *map(str, args)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        else:
            self.assertGreater(p.returncode, 0, p.stderr)
            self.assertNotIn("Sanitizer", p.stderr)
        return p

    def assemble(self, name, source, *flags):
        path = self.dir / (name + ".mica")
        out = self.dir / (name + (".o" if "-c" in flags else ".bin"))
        path.write_text(source)
        self.command("mica-as", *flags, path, "-o", out)
        return out

    def run_image(self, image, *flags):
        return self.command("mica-run", *flags, image)

    def test_crc_and_uart_devices(self):
        import binascii

        rng = random.Random(0xC32)
        data = bytes(rng.randrange(256) for _ in range(257))
        self.command(
            "mica-as",
            "--trap",
            ROOT / "examples/peripherals32.mica",
            "-o",
            self.dir / "peripherals.bin",
        )
        p = self.run_image(
            self.dir / "peripherals.bin", "--trap", "--uart-input", "414243"
        )
        self.assertEqual(p.stdout, "ABC")
        self.assertIn("x1=0x2a", p.stderr)
        for width in [32, 64]:
            source = "li32 x5,0xffff0040\nli8 x1,1\nstw x1,[x5]\n"
            for byte in data:
                source += f"li32 x1,{byte}\nstb x1,[x5+4]\n"
            source += "ldw x1,[x5+8]\nldw x2,[x5+12]\nldbu x3,[x5+8]\nwfi\n"
            image = self.assemble("crc" + str(width), source, "--xlen", width)
            p = self.run_image(image, "--xlen", width)
            crc = binascii.crc32(data)
            self.assertIn(f"x1=0x{crc:x}", p.stderr)
            self.assertIn("x2=0x101", p.stderr)
            self.assertIn(f"x3=0x{crc & 255:x}", p.stderr)
        image = self.assemble(
            "uart",
            "li32 x4,0xffff0010\nldw x1,[x4+8]\nldbu x2,[x4+4]\nldbu x3,[x4+4]\nldbu x5,[x4+4]\nldw x6,[x4+8]\nwfi\n",
        )
        p = self.run_image(image, "--uart-input", "00fF")
        for text in ["x1=0x209", "x2=0x0", "x3=0xff", "x5=0x0", "x6=0x8"]:
            self.assertIn(text, p.stderr)
        for malformed in ["0", "xx", "00" * 17]:
            self.command("mica-run", "--uart-input", malformed, image, ok=False)

    def test_separate_compilation_and_conversion(self):
        for width in [32, 64]:
            flags = ["--xlen", str(width), "-c"]
            start = self.assemble(
                "start",
                f".arch mica{width}\n.global _start\n.extern helper\n_start: li8 x1,40\ncall helper\nwfi\n",
                *flags,
            )
            helper = self.assemble(
                "helper",
                f".arch mica{width}\n.global helper\nhelper: addi x1,2\nret\n",
                *flags,
            )
            binary, elf = self.dir / "out.bin", self.dir / "out.elf"
            self.command("mica-ld", start, helper, "-o", binary, "--elf", elf)
            first = (binary.read_bytes(), elf.read_bytes())
            self.command("mica-ld", start, helper, "-o", binary, "--elf", elf)
            self.assertEqual(first, (binary.read_bytes(), elf.read_bytes()))
            self.assertIn("x1=0x2a", self.run_image(elf, "--xlen", width).stderr)
            self.assertIn("helper", self.command("mica-nm", helper).stdout)
            self.assertIn("PCREL24", self.command("mica-objdump", start).stdout)
            self.assertIn("addi", self.command("mica-dis", elf).stdout)
            copy = self.dir / "copy.bin"
            self.command("mica-objcopy", "-O", "binary", elf, copy)
            self.assertEqual(binary.read_bytes(), copy.read_bytes())
            for fmt in ["mem8", "ihex"]:
                self.command("mica-objcopy", "-O", fmt, elf, copy)
                self.assertTrue(copy.stat().st_size)
            self.command("mica-run", start, ok=False)

    def test_all_relocations(self):
        # Absolute addresses, local addresses and every relative field width.
        start = self.assemble(
            "relocs",
            """.arch mica64
.global _start
.extern target
_start: li32 x1,target+2
li64 x2,target
li8 x3,1
bz x0,target
bnz x3,target
b target
beq x1,x2,target
dbnz x3,target
j target
call target
local: .word target+4,local
.quad target+8
""",
            "-c",
            "--xlen",
            "64",
            "--flow",
        )
        end = self.assemble(
            "target",
            ".arch mica64\n.global target\ntarget: wfi\n",
            "-c",
            "--xlen",
            "64",
        )
        out = self.dir / "linked.bin"
        self.command("mica-ld", start, end, "-o", out, "--elf", self.dir / "linked.elf")
        table = self.command("mica-objdump", start).stdout
        for name in [
            "ABS32",
            "ABS64",
            "LI32",
            "LI64",
            "PCREL8",
            "PCREL11",
            "PCREL14",
            "PCREL20",
            "PCREL24",
        ]:
            self.assertIn(name, table)
        image = out.read_bytes()
        target = len(image) - 2
        # Executed li32/64 then taken bz; relocation data must resolve exactly.
        p = self.run_image(self.dir / "linked.elf", "--xlen", 64, "--flow")
        self.assertIn(f"x1=0x{target+2:x}", p.stderr)
        self.assertIn(f"x2=0x{target:x}", p.stderr)
        self.assertEqual(int.from_bytes(image[56:60], "little"), target + 4)

    def test_linker_errors_and_weak_symbols(self):
        a = self.assemble(
            "a", ".global _start\n.extern missing\n_start: call missing\nwfi\n", "-c"
        )
        self.assertIn(
            "undefined symbol",
            self.command("mica-ld", a, "-o", self.dir / "o", ok=False).stderr,
        )
        b = self.assemble("b", ".global _start\n_start: wfi\n", "-c")
        self.command("mica-ld", b, b, "-o", self.dir / "o", ok=False)
        c = self.assemble(
            "c", ".weak optional\n.global _start\n_start: li32 x1,optional\nwfi\n", "-c"
        )
        self.command("mica-ld", c, "-o", self.dir / "o")
        self.assertIn("x1=0x0", self.run_image(self.dir / "o").stderr)
        far = self.assemble("far", ".global target\n.space 1024\ntarget: wfi\n", "-c")
        near = self.assemble(
            "near", ".global _start\n_start: bz x1,target\nwfi\n", "-c"
        )
        self.assertIn(
            "out of range",
            self.command("mica-ld", near, far, "-o", self.dir / "o", ok=False).stderr,
        )

    def test_malformed_elf(self):
        obj = self.assemble("elf", ".global _start\n_start: wfi\n", "-c").read_bytes()
        rng = random.Random(0x1CA)
        samples = [obj[:n] for n in [0, 1, 4, 16, 63, 64, len(obj) - 1]]
        for offset in [4, 5, 18, 40, 48, 58, 60, 62]:
            b = bytearray(obj)
            b[offset : offset + 2] = b"\xff\xff"
            samples.append(bytes(b))
        for _ in range(20):
            samples.append(rng.randbytes(rng.randrange(1, 1024)))
        for data in samples:
            path = self.dir / "bad.o"
            path.write_bytes(data)
            self.command("mica-objdump", path, ok=False)
            self.command("mica-ld", path, "-o", self.dir / "bad.bin", ok=False)

    def test_disassembly_byte_comments(self):
        image = self.assemble("bytes", "li8 x1,1\nwfi\n")
        text = self.command("mica-dis", image).stdout
        self.assertIn("; 0141", text)
        self.assertIn("; 8004", text)

    def test_lossless_disassembly(self):
        # Includes every short halfword plus random long envelopes and odd tails.
        rng = random.Random(441)
        for width in [32, 64]:
            image = b"".join(
                n.to_bytes(2, "little") for n in range(65536)
            ) + rng.randbytes(8193)
            path = self.dir / "round.bin"
            path.write_bytes(image)
            text = self.command("mica-dis", "--assembly", "--xlen", width, path).stdout
            result = self.assemble(
                "round",
                text,
                "--mica2",
                "--xlen",
                str(width),
                "--xreg",
                "--mul",
                "--flow",
                "--bitops",
                "--atomic",
                "--simd",
                "--trap",
            )
            self.assertEqual(image, result.read_bytes())

    def test_expression_and_preprocessor_limits(self):
        data = self.dir / "data.dat"
        data.write_bytes(b"\x12\x34")
        output = self.assemble(
            "pre",
            '.const N,2\n.if N\n.repeat N\n.byte 7\n.endrepeat\n.else\n.error "inactive"\n.endif\n.incbin "data.dat"\n',
        )
        self.assertEqual(output.read_bytes(), b"\x07\x07\x12\x34")
        source = self.dir / "deep.mica"
        source.write_text(".word " + "(" * 300 + "1" + ")" * 300)
        self.assertIn("nesting", self.command("mica-as", source, ok=False).stderr)

    def test_mixed_width_reservation(self):
        source = """.arch mica64
li32 x1,1024
lr.q x2,[x1]
li8 x3,42
sc.w x4,x3,[x1]
ldq x5,[x1]
wfi
"""
        binary = self.assemble("reservation", source, "--xlen", "64", "--atomic")
        p = self.run_image(binary, "--xlen", "64", "--atomic")
        self.assertIn("x4=0x1", p.stderr)
        self.assertIn("x5=0x0", p.stderr)

    def test_precise_fault_and_step_budget(self):
        source = """li32 x5,handler
csrw tvec,x5
li8 x1,55
jalr x1
wfi
handler: csrr x2,epc
csrr x3,cause
csrr x4,tval
wfi
"""
        binary = self.assemble("fault", source, "--trap")
        trace = self.dir / "trace.jsonl"
        p = self.run_image(binary, "--trap", "--retire-trace", trace)
        self.assertIn("x6=0x0", p.stderr)
        records = [json.loads(s) for s in trace.read_text().splitlines()]
        fault = next(r for r in records if r["trap"])
        self.assertFalse(fault["retired"])
        self.assertEqual(fault["cause"], 0)
        self.assertEqual(fault["regs"], fault["before"])
        one = self.assemble("one", "wfi\n")
        self.run_image(one, "--steps", "1")

    def test_bounded_copy_ranges(self):
        libraries = "\n".join(
            f'.include "{ROOT / "stdlib" / name}"'
            for name in ["bounded32.mica", "flow.mica"]
        )
        for count, expected in [(4, 0x44332211), (5, 0)]:
            source = f"li32 x1,dst\nli32 x2,src\nli8 x3,{count}\nli32 x4,dst+4\nli32 x5,src+4\ncall mica_memcpy_bounded\nli32 x4,dst\nldw x2,[x4]\nwfi\n{libraries}\n.align 4\nsrc: .word 0x44332211\ndst: .word 0\n"
            image = self.assemble("bounded", source, "--flow")
            result = self.run_image(image, "--flow")
            self.assertIn(f"x2=0x{expected:x}", result.stderr)

    def test_fir_against_independent_reference(self):
        source = ROOT / "examples/fir32.mica"
        binary, symbols = self.dir / "fir.bin", self.dir / "fir.map"
        self.command("mica-as", "--mul", source, "-o", binary, "--map", symbols)
        address = next(
            int(line.split()[0], 16)
            for line in symbols.read_text().splitlines()
            if line.endswith(" results")
        )
        result = self.run_image(binary, "--mul", "--peek", f"{address}:16")
        raw = bytes.fromhex(
            re.search(r"MEM\[0x[0-9a-f]+\]=([0-9a-f]+)", result.stderr)[1]
        )
        samples, coefficients = [1, -2, 3, 4, -5, 6, 7], [2, -3, 4, -1]
        expected = [
            sum(samples[i + j] * coefficients[j] for j in range(4)) & 0xFFFFFFFF
            for i in range(4)
        ]
        actual = [int.from_bytes(raw[i : i + 4], "little") for i in range(0, 16, 4)]
        self.assertEqual(expected, actual)

    def test_profile_and_debugger(self):
        image = self.assemble(
            "debug", "li8 x1,40\naddi x1,2\nwfi\n", "--profile", "MICA-C"
        )
        result = subprocess.run(
            [str(TOOLS / "mica-run"), "--debug", str(image)],
            input="step\nsetreg 2 99\nbreak 4\ncontinue\nregs\nquit\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("x1=0x2a", result.stderr)
        self.assertIn("x2=0x63", result.stderr)
        self.command("mica-run", "--profile", "MICA-MP", image, ok=False)

    def test_timer_interrupt(self):
        source = """li32 x5,handler
csrw tvec,x5
li8 x1,0
csrw cmp_hi,x1
li8 x1,100
csrw cmp_lo,x1
li8 x1,2
csrw ie,x1
li8 x1,1
csrw status,x1
loop: addi x3,1
b loop
handler: csrr x4,cause
li8 x1,42
wfi
"""
        binary = self.assemble("timer", source, "--trap")
        p = self.run_image(binary, "--trap")
        self.assertIn("x4=0x80000002", p.stderr)
        self.assertIn("x1=0x2a", p.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    TOOLS = args.tools.resolve()
    unittest.main(argv=[__file__, *remaining], verbosity=2)
