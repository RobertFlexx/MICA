#!/usr/bin/env python3
"""SDK end-to-end tests: machine code generation, execution, libraries and errors."""

import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import random

ROOT = Path(__file__).resolve().parents[1]
ASM = os.getenv("MICA_AS", str(ROOT / "build/mica-as"))
RUN = os.getenv("MICA_RUN", str(ROOT / "build/mica-run"))
DIS = os.getenv("MICA_DIS", str(ROOT / "build/mica-dis"))


class SDKTest(unittest.TestCase):
    def asm(self, source, opts=(), expect_ok=True, listing=False, hexfile=False):
        path = Path(self.tmp.name) / "test.mica"
        path.write_text(source)
        outfile = Path(self.tmp.name) / "test.bin"
        args = [ASM, *opts, "-o", str(outfile)]
        if listing:
            args += ["--listing", str(path.with_suffix(".lst"))]
        if hexfile:
            args += ["--hex", str(path.with_suffix(".hex"))]
        proc = subprocess.run([*args, str(path)], capture_output=True, text=True)
        if expect_ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return outfile.read_bytes()
        self.assertNotEqual(proc.returncode, 0, "expected failure: " + source)
        return proc.stderr

    def example(self, basename, flags=(), peek=None):
        filename = ROOT / "examples" / basename
        out = Path(self.tmp.name) / (filename.stem + ".bin")
        a = subprocess.run(
            [ASM, *flags, "-o", str(out), str(filename)], capture_output=True, text=True
        )
        self.assertEqual(a.returncode, 0, a.stderr)
        args = [RUN, *flags]
        if peek:
            args += ["--peek", peek]
        p = subprocess.run([*args, str(out)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return (
            {
                int(k): int(v, 16)
                for k, v in re.findall(r"\bx(\d+)=0x([0-9a-f]+)", p.stderr)
            },
            p.stdout,
            p.stderr,
        )

    def runsource(self, source, flags=(), peek=None, expect_ok=True):
        binary = self.asm(source, flags)
        f = Path(self.tmp.name) / "test.bin"
        args = [RUN, *flags]
        if peek:
            args += ["--peek", peek]
        p = subprocess.run([*args, str(f)], capture_output=True, text=True)
        if expect_ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return {
            int(k): int(v, 16)
            for k, v in re.findall(r"\bx(\d+)=0x([0-9a-f]+)", p.stderr)
        }, p

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_bitops_examples_and_feature_discovery(self):
        r, _, _ = self.example("bitops32.mica", ["--bitops"])
        self.assertEqual(
            (r[1], r[2], r[3], r[4], r[5], r[6]), (32 | 128, 0, 0, 0, 8, 0xFF000000)
        )
        r, _, _ = self.example("bitops64.mica", ["--xlen", "64", "--bitops"])
        self.assertEqual(
            (r[1], r[3], r[4], r[5], r[6]),
            (32 | 128, 0xEFCDAB8967452301, 0xEF0123456789ABCD, 32, 7),
        )
        r, _ = self.runsource(
            ".arch mica64\ncsrr x1,arch\ncsrr x2,features\nwfi\n", ["--xlen", "64"]
        )
        self.assertEqual((r[1], r[2]), (64, 128))
        r, _ = self.runsource(
            ".arch mica32\ncsrr x1,features\nwfi\n", ["--flow", "--mul", "--bitops"]
        )
        self.assertEqual(r[1], 2 | 4 | 32 | 128)

    def test_bitops_randomized_reference(self):
        def signed(a, w):
            return a - (1 << w) if a >> (w - 1) else a

        def oracle(op, a, b, w):
            mask = (1 << w) - 1
            shift = b & (w - 1)
            if op == "clz3":
                return w - a.bit_length()
            if op == "ctz3":
                return ((a & -a).bit_length() - 1) if a else w
            if op == "popcnt3":
                return a.bit_count()
            if op == "rev8":
                return int.from_bytes(a.to_bytes(w // 8, "little"), "big")
            if op == "ror3":
                return ((a >> shift) | (a << ((w - shift) & (w - 1)))) & mask
            if op == "rol3":
                return ((a << shift) | (a >> ((w - shift) & (w - 1)))) & mask
            if op == "min3":
                return a if signed(a, w) < signed(b, w) else b
            if op == "max3":
                return a if signed(a, w) > signed(b, w) else b
            if op == "minu3":
                return min(a, b)
            if op == "maxu3":
                return max(a, b)
            if op == "bset3":
                return a | (1 << shift)
            if op == "bclr3":
                return a & ~(1 << shift)
            if op == "binv3":
                return a ^ (1 << shift)
            if op == "bext3":
                return (a >> shift) & 1
            if op == "andn3":
                return a & ~b
            if op == "orn3":
                return a | ~b
            if op == "xnor3":
                return ~(a ^ b)
            if op == "sextb3":
                return signed(a & 255, 8)
            if op == "sexth3":
                return signed(a & 65535, 16)
            if op == "zexth3":
                return a & 65535
            raise AssertionError(op)

        rand = random.Random(0x4D494341)
        unary = {"clz3", "ctz3", "popcnt3", "rev8", "sextb3", "sexth3", "zexth3"}
        ops = [
            "clz3",
            "ctz3",
            "popcnt3",
            "rev8",
            "ror3",
            "rol3",
            "min3",
            "max3",
            "minu3",
            "maxu3",
            "bset3",
            "bclr3",
            "binv3",
            "bext3",
            "andn3",
            "orn3",
            "xnor3",
            "sextb3",
            "sexth3",
            "zexth3",
        ]
        for w in (32, 64):
            flags = ["--bitops", "--xlen", str(w)]
            for op in ops:
                for a, b in [
                    (0, 0),
                    ((1 << w) - 1, w),
                    (rand.getrandbits(w), rand.getrandbits(w)),
                ]:
                    asm = "li32" if w == 32 else "li64"
                    operands = "x3,x1" if op in unary else "x3,x1,x2"
                    source = f".arch mica{w}\n{asm} x1,{a}\n{asm} x2,{b}\n{op} {operands}\nwfi\n"
                    r, _ = self.runsource(source, flags)
                    self.assertEqual(
                        r[3], oracle(op, a, b, w) & ((1 << w) - 1), (w, op, a, b)
                    )

    def test_bitops_encodings_errors_and_disassembly(self):
        binary = self.asm(
            ".arch mica32\npopcnt3 x3,x1\nror3 x4,x1,x2\nwfi\n", ["--bitops"]
        )
        self.assertEqual(len(binary), 10)
        import shutil

        tool = DIS
        proc = subprocess.run(
            [tool, str(Path(self.tmp.name) / "test.bin")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("popcnt3 x3,x1", proc.stdout)
        self.assertIn("ror3 x4,x1,x2", proc.stdout)
        for source, flags in [
            ("popcnt3 x1,x2\n", []),
            ("popcnt3 x1,x2,x3\n", ["--bitops"]),
            ("ror3 x1,x2\n", ["--bitops"]),
            ("clz3 x8,x1\n", ["--bitops"]),
        ]:
            with self.subTest(source=source):
                self.asm(".arch mica32\n" + source, flags, expect_ok=False)
        # Hardware feature registers cannot be rewritten by firmware.
        r, p2 = self.runsource(
            ".arch mica32\nli8 x1,8\ncsrw features,x1\nwfi\n", [], expect_ok=False
        )
        self.assertEqual(p2.returncode, 2)
        self.assertIn("read-only", p2.stderr)

    def test_buffer_library_memxor(self):
        path = (ROOT / "stdlib/buffer.mica").as_posix()
        for w in (32, 64):
            source = f""".arch mica{w}
li32 x1,dst
li32 x2,src
li8 x3,4
li8 x5,27
call mica_memxor
li32 x2,dst
ldbu x3,[x2+0]
ldbu x4,[x2+3]
wfi
.include "{path}"
src: .byte 0x12,0x23,0x34,0x45
dst: .byte 0x11,0x22,0x33,0x44
"""
            regs, _ = self.runsource(source, ["--xlen", str(w)])
            self.assertEqual((regs[3], regs[4], regs[5]), (3, 1, 27))

    def test_bitops_runtime_helpers(self):
        path = (ROOT / "stdlib/bits_hw.mica").as_posix()
        for w in (32, 64):
            source = (
                f'.arch mica{w}\nli8 x1,0\ncall mica_ctz_b\nwfi\n.include "{path}"\n'
            )
            regs, _ = self.runsource(source, ["--xlen", str(w), "--bitops"])
            self.assertEqual(regs[1], w)

    def test_trap_software_exception_and_irq(self):
        regs, _, _ = self.example("trap32.mica", ["--trap"])
        self.assertEqual((regs[3], regs[4]), (18, 11))
        regs, _, _ = self.example("trap_irq32.mica", ["--trap"])
        self.assertEqual((regs[3], regs[4], regs[5]), (12, 42, 0x80000001))
        # Same encoding works with widened scalar architecture.
        path = ROOT / "examples/trap32.mica"
        regs, _ = self.runsource(
            path.read_text().replace("mica32", "mica64"), ["--trap", "--xlen", "64"]
        )
        self.assertEqual((regs[3], regs[4]), (18, 11))

    def test_trap_errors_and_interrupt_mask(self):
        _, proc = self.runsource(
            ".arch mica32\neret\nwfi\n", ["--trap"], expect_ok=False
        )
        self.assertIn("eret outside trap", proc.stderr)
        _, proc = self.runsource(
            ".arch mica32\necall\nwfi\n", ["--trap"], expect_ok=False
        )
        self.assertIn("invalid trap vector", proc.stderr)
        source = """.arch mica32
li32 x1, handler
csrw tvec,x1
li8 x2,1
csrw ip,x2
csrw ie,x2
li8 x3,23
wfi
handler:
li8 x3,99
eret
"""
        regs, _ = self.runsource(source, ["--trap"])
        self.assertEqual(regs[3], 23)  # interrupts disabled by default

    def test_trap_feature_discovery(self):
        regs, _ = self.runsource(
            ".arch mica64\ncsrr x1,features\ncsrr x2,arch\nwfi\n",
            ["--xlen", "64", "--bitops", "--trap"],
        )
        self.assertEqual((regs[1], regs[2]), (32 | 64 | 128, 64))

    def test_buffer_memeq_and_zero(self):
        path = (ROOT / "stdlib/buffer.mica").as_posix()
        for w in (32, 64):
            for buf, equal in [('"abc"', 1), ('"abd"', 0)]:
                source = f""".arch mica{w}
li32 x1,first
li32 x2,second
li8 x3,3
li8 x5,99
call mica_memeq_full
mov x4,x1
li32 x1,first
li8 x2,3
call mica_memzero
li32 x2,first
ldbu x3,[x2+2]
wfi
.include "{path}"
first: .ascii "abc"
second: .ascii {buf}
"""
                regs, _ = self.runsource(source, ["--xlen", str(w)])
                self.assertEqual((regs[4], regs[3], regs[5]), (equal, 0, 99))

    def test_instruction_retirement_counter(self):
        src = ".arch mica32\ncsrr x1,instret_lo\nli8 x2,55\ncsrr x3,instret_lo\nwfi\n"
        regs, proc = self.runsource(src)
        self.assertEqual((regs[1], regs[2], regs[3]), (0, 55, 2))
        self.assertIn("retired=4", proc.stderr)
        self.assertNotIn(" cycles=", proc.stderr)
        _, proc = self.runsource(
            ".arch mica32\ncsrw instret_lo,x1\nwfi\n", expect_ok=False
        )
        self.assertIn("read-only", proc.stderr)

    def test_examples_32(self):
        r, _, _ = self.example("arithmetic32.mica")
        self.assertEqual((r[1], r[4]), (42, 42))
        r, out, _ = self.example("hello32.mica")
        self.assertEqual(out, "Hi\n")
        self.assertEqual(r[1], 42)
        r, _, _ = self.example("macros.mica")
        self.assertEqual((r[1], r[2]), (0, 0))
        r, _, _ = self.example("string32.mica")
        self.assertEqual(r[1], 4)
        r, _, _ = self.example("atomic32.mica", ["--atomic"])
        self.assertEqual(r[1], 8)
        r, _, _ = self.example("div32.mica")
        self.assertEqual((r[1], r[2]), (858993459, 0))

    def test_examples_64(self):
        r, _, _ = self.example("arithmetic64.mica", ["--xlen", "64"])
        expected = (0x0123456789ABCDEF + 0xFFFFFFFF) & ((1 << 64) - 1)
        self.assertEqual(r[1], expected)
        self.assertEqual(r[2], (0xFFFFFFFF00000000 | ((expected) & 0xFFFFFFFF)))
        self.assertEqual(r[3], expected & 0xFFFFFFFF)
        r, _, _ = self.example("div64.mica", ["--xlen", "64"])
        self.assertEqual((r[1], r[2]), divmod(0x10000000005, 3))

    def test_vector_add_memory(self):
        r, _, stderr = self.example("vector32.mica", ["--simd"], "0x60:16")
        match = re.search(r"MEM\[0x60\]=([0-9a-f]+)", stderr)
        self.assertIsNotNone(match, stderr)
        self.assertEqual(
            bytes.fromhex(match.group(1)),
            bytes(
                [11, 22, 33, 44, 55, 66, 77, 88, 99, 110, 121, 132, 143, 154, 165, 176]
            ),
        )

    def test_li32_signs(self):
        for val in [
            "0",
            "127",
            "-128",
            "128",
            "32767",
            "-32768",
            "0xabcdef11",
            "-2147483648",
            "4294967295",
        ]:
            source = f".arch mica32\nli x1, {val}\nwfi\n"
            r, _ = self.runsource(source)
            self.assertEqual(r[1], int(val, 0) & 0xFFFFFFFF, val)

    def test_64bit_constants(self):
        for val in [
            "-1",
            "0",
            "12345",
            "0x8000000000000000",
            "0xfedcba9876543210",
            "0x1234567800000000",
        ]:
            r, _ = self.runsource(
                f".arch mica64\nli64 x1, {val}\nwfi\n", ["--xlen", "64"]
            )
            self.assertEqual(r[1], int(val, 0) & ((1 << 64) - 1), val)

    def test_math_library_random_32(self):
        lib = (ROOT / "stdlib/math32.mica").as_posix()
        random.seed(91)
        for a, b in [(0, 1), (10, 3), (1234567890, 65535), (4294967295, 0)] + [
            (random.getrandbits(32), random.randrange(1, 2**32)) for _ in range(10)
        ]:
            src = f'.arch mica32\nli32 x1, {a}\nli32 x2, {b}\ncall mica_udivmod\nwfi\n.include "{lib}"\n'
            r, _ = self.runsource(src)
            quotient, remainder = (0, a) if b == 0 else divmod(a, b)
            self.assertEqual((r[1], r[2]), (quotient, remainder), (a, b))

    def test_math_library_random_64(self):
        lib = (ROOT / "stdlib/math64.mica").as_posix()
        random.seed(342)
        for a, b in [(0, 7), (2**64 - 1, 3), (2**64 - 1, 0)] + [
            (random.getrandbits(64), random.randrange(1, 2**64)) for _ in range(9)
        ]:
            src = f'.arch mica64\nli64 x1, {a}\nli64 x2, {b}\ncall mica_udivmod\nwfi\n.include "{lib}"\n'
            r, _ = self.runsource(src, ["--xlen", "64"])
            q, re = (0, a) if b == 0 else divmod(a, b)
            self.assertEqual((r[1], r[2]), (q, re), (a, b))

    def test_memmove_overlap(self):
        lib = (ROOT / "stdlib/string.mica").as_posix()
        src = f"""\n.arch mica32
li32 x1, data
addi x1, 2
li32 x2, data
li8 x3, 4
call mica_memmove
li32 x1, data
ldbu x2, [x1+2]
ldbu x3, [x1+5]
wfi
.include "{lib}"
.align 4
data: .ascii "abcdef"
"""
        r, _ = self.runsource(src)
        self.assertEqual((r[2], r[3]), (ord("a"), ord("d")))

    def test_string_library_cmp(self):
        lib = (ROOT / "stdlib/string.mica").as_posix()
        for word, expected in [("abc", 0), ("abb", 1), ("abd", 0xFFFFFFFF)]:
            src = f'.arch mica32\nli32 x1, word1\nli32 x2, word2\ncall mica_strcmp\nwfi\n.include "{lib}"\nword1: .asciz "abc"\nword2: .asciz "{word}"\n'
            r, _ = self.runsource(src)
            self.assertEqual(r[1], expected)

    def test_atomic64(self):
        lib = (ROOT / "stdlib/atomic64.mica").as_posix()
        src = f'.arch mica64\nli32 x1, data\nli8 x2, 11\ncall mica_fetch_add\nwfi\n.include "{lib}"\n.align 8\ndata: .quad 10000000000\n'
        r, _ = self.runsource(src, ["--xlen", "64", "--atomic"])
        self.assertEqual(r[1], 10000000000)

    def test_all_xlen_extensions(self):
        src = """.arch mica64
li8 x1, 5
li8 x2, 10
add3 x9, x1, x2
subw3 x10, x9, x2
mulw3 x11, x9, x2
li64 x12, 0xffffffffffffffff
addw3 x13, x12, x2
sltu3 x14, x1, x2
mov x3, x2
wfi
"""
        r, _ = self.runsource(src, ["--xlen", "64", "--xreg", "--mul"])
        self.assertEqual((r[9], r[10], r[11], r[13], r[14]), (15, 5, 150, 9, 1))

    def test_branches(self):
        src = """.arch mica32
li8 x1, 11
li8 x2, 0
loop:
add x2, x1
addi x1, -1
bnz x1, loop
li8 x3, 66
beq x2, x3, good
li8 x4, 99
b done
good: li8 x4, 42
done: wfi
"""
        r, _ = self.runsource(src)
        self.assertEqual((r[2], r[4]), (66, 42))

    def test_macro_repeat(self):
        src = """.arch mica32
.macro bump a
    addi $a, 1
.endm
li8 x1, 0
.repeat 12
bump x1
.endrepeat
wfi
"""
        r, _ = self.runsource(src)
        self.assertEqual(r[1], 12)

    def test_endian_and_hex(self):
        src = ".arch mica32\nli8 x1, -1\nwfi\n.word 0x12345678\n"
        blob = self.asm(src, listing=True, hexfile=True)
        self.assertEqual(blob[0:2], bytes.fromhex("ff41"))
        self.assertEqual(blob[-4:], bytes.fromhex("78563412"))
        records = (Path(self.tmp.name) / "test.hex").read_text().splitlines()
        for line in records:
            self.assertTrue(line.startswith(":"))
            raw = bytes.fromhex(line[1:])
            self.assertEqual(sum(raw) & 255, 0, line)

    def test_invalid_rejected(self):
        for program, flags in [
            (".arch mica32\nvadd.u8 v0,v1,v2\n", ()),
            (".arch mica32\nldq x1,[x2]\n", ()),
            (".arch mica64\naddw3 x1,x2,x3\n", ()),
            (".arch mica32\nli8 x1, 128\n", ()),
            (".arch mica32\nli8 x1, missing\n", ()),
            (".arch mica32\nbeq x1,x2,5\n", ()),
            (".arch mica32\nldw x1,[x2+3]\n", ()),
            (".arch mica32\nadd3 x8,x1,x2\n", ()),
            (".arch mica32\nli32 x1, 0x100000000\n", ()),
            (".arch mica32\n.byte 256\n", ()),
            (".arch mica32\n.macro foo a\n nop\n", ()),
        ]:
            with self.subTest(program=program):
                self.asm(program, flags, expect_ok=False)

    def test_console_libraries(self):
        _, out, _ = self.example("console32.mica")
        self.assertEqual(out, "MICA32: 1234CAFE\n")
        _, out, _ = self.example("console64.mica", ["--xlen", "64"])
        self.assertEqual(out, "MICA64: 0123456789ABCDEF\n")

    def test_ascii_ctype(self):
        library = (ROOT / "stdlib/ctype.mica").as_posix()
        cases = [
            ("mica_isdigit", ord("7"), 1),
            ("mica_isdigit", ord("!"), 0),
            ("mica_islower", ord("z"), 1),
            ("mica_islower", ord("A"), 0),
            ("mica_isupper", ord("G"), 1),
            ("mica_isupper", ord("g"), 0),
            ("mica_tolower", ord("F"), ord("f")),
            ("mica_tolower", ord("q"), ord("q")),
            ("mica_toupper", ord("e"), ord("E")),
            ("mica_toupper", ord("B"), ord("B")),
        ]
        for method, value, expected in cases:
            with self.subTest(method=method, value=value):
                src = f'.arch mica32\nli8 x1, {value}\ncall {method}\nwfi\n.include "{library}"\n'
                regs, _ = self.runsource(src)
                self.assertEqual(regs[1], expected)

    def test_store_invalidates_partial_reservation(self):
        source = """.arch mica32
li32 x1, data
lr.w x2, [x1]
li8 x3, 7
stb x3, [x1+1]
li8 x3, 100
sc.w x4, x3, [x1]
ldw x5, [x1]
wfi
.align 4
data: .word 0x11223344
"""
        regs, _ = self.runsource(source, ["--atomic"])
        self.assertEqual((regs[4], regs[5]), (1, 0x11220744))

    def test_flow_copy_32_and_64(self):
        r, _, _ = self.example("flow_copy32.mica", ["--flow"])
        self.assertEqual((r[1], r[2], r[3]), (3, 24, 0))
        r, _, _ = self.example("flow_copy64.mica", ["--xlen", "64", "--flow"])
        self.assertEqual(r[1], 0x0000000200000001)

    def test_flow_compact_byte_footprint(self):
        src = ".arch mica32\nldpi.b x4,[x2]\nstpi.b x4,[x1]\ndbnz x3, 0\n"
        data = self.asm(src, ["--flow"])
        self.assertEqual(len(data), 8)
        self.assertEqual(data[:4], bytes([0xE2, 0x05, 0xE1, 0x06]))
        self.asm(src, expect_ok=False)

    def test_flow_extended_stride_and_faults(self):
        src = """.arch mica64
li32 x2, sample
ldpi.h x1,[x2],4
ldpi.h x3,[x2],-4
wfi
.align 4
sample: .half 0x1234,0x5678,0xabcd,0xef01
"""
        r, _ = self.runsource(src, ["--xlen", "64", "--flow"])
        self.assertEqual((r[1], r[3]), (0x1234, 0xABCD))
        for source, flags in [
            ("ldpi.w x1,[x1]\n", ["--flow"]),
            ("stpi.h x1,[x0]\n", ["--flow"]),
            ("ldpi.q x1,[x2]\n", ["--flow"]),
            ("ldpi.b x1,[x2],8192\n", ["--flow"]),
            ("dbnz x8, here\nhere: wfi\n", ["--flow"]),
        ]:
            with self.subTest(source=source):
                self.asm(".arch mica32\n" + source, flags, expect_ok=False)

    def test_flow_preserves_memcpy_abi(self):
        lib = (ROOT / "stdlib/flow.mica").as_posix()
        source = f""".arch mica32
li32 x1,dst
li32 x2,src
li8 x3,4
li8 x5,57
call mica_memcpy_flow
li32 x4,dst
ldbu x2,[x4+3]
wfi
.include "{lib}"
src: .byte 1,2,3,4
dst: .space 4
"""
        r, _ = self.runsource(source, ["--flow"])
        self.assertEqual((r[2], r[5]), (4, 57))

    def test_extended_string_helpers(self):
        lib = (ROOT / "stdlib/strings_extra.mica").as_posix()
        for name, args, result in [
            ("mica_strncmp", "li32 x1,a\nli32 x2,b\nli8 x3,2", 0),
            ("mica_strncmp", "li32 x1,a\nli32 x2,b\nli8 x3,3", 0xFFFFFFFF),
            ("mica_memchr", "li32 x1,a\nli8 x2,98\nli8 x3,3", None),
        ]:
            source = f'.arch mica32\n{args}\ncall {name}\nwfi\n.include "{lib}"\na: .asciz "abc"\nb: .asciz "abd"\n'
            r, _ = self.runsource(source)
            if result is not None:
                self.assertEqual(r[1], result)
            else:
                self.assertNotEqual(r[1], 0)

    def test_crc32_known_answer(self):
        lib = (ROOT / "stdlib/checksum32.mica").as_posix()
        source = f'.arch mica32\nli32 x1,data\nli8 x2,9\ncall mica_crc32\nwfi\n.include "{lib}"\ndata: .ascii "123456789"\n'
        r, _ = self.runsource(source)
        self.assertEqual(r[1], 0xCBF43926)

    def test_arena_alloc_32_64(self):
        for profile, flags in [
            ("arena32.mica", []),
            ("arena64.mica", ["--xlen", "64"]),
        ]:
            with self.subTest(profile=profile):
                regs, _, _ = self.example(profile, flags)
                self.assertNotEqual(regs[4], 0)
                self.assertEqual(regs[4], regs[5] + 16)
                self.assertEqual(regs[3], regs[5] + 64)  # No cursor change on failure.
                self.assertEqual(regs[1], 0)  # Request after the 64-byte arena fills.

    def test_flow_word_and_q_store(self):
        source = """.arch mica64
li32 x2, src
li32 x3, dst
ldpi.q x1,[x2],16
stpi.q x1,[x3],8
addi x3,-8
ldq x4,[x3]
wfi
.align 8
src: .quad 0x1122334455667788,0xaabbccddeeff0011
dst: .quad 0,0
"""
        r, _ = self.runsource(source, ["--flow", "--xlen", "64"])
        self.assertEqual((r[1], r[4]), (0x1122334455667788, 0x1122334455667788))

    def test_crc32_empty_input(self):
        lib = (ROOT / "stdlib/checksum32.mica").as_posix()
        source = f'.arch mica32\nli32 x1,data\nli8 x2,0\ncall mica_crc32\nwfi\n.include "{lib}"\ndata: .byte 42\n'
        r, _ = self.runsource(source)
        self.assertEqual(r[1], 0)

    def test_flow_zero_length_is_noop(self):
        for name, flags in [
            ("flow_copy32.mica", ["--flow"]),
            ("flow_copy64.mica", ["--xlen", "64", "--flow"]),
        ]:
            src = (ROOT / "examples" / name).read_text()
            src = src.replace("li8 x3, 8", "li8 x3, 0").replace(
                "li8 x3, 4", "li8 x3, 0"
            )
            source = Path(self.tmp.name) / name
            source.write_text(
                src.replace(
                    "../stdlib/flow.mica", (ROOT / "stdlib/flow.mica").as_posix()
                )
            )
            out = Path(self.tmp.name) / (name + ".bin")
            proc = subprocess.run(
                [ASM, *flags, str(source), "-o", str(out)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            p = subprocess.run([RUN, *flags, str(out)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)

    def test_disassembler_mnemonics(self):
        from shutil import which

        tool = os.environ.get("MICA_DIS", str(ROOT / "build/mica-dis"))
        if not Path(tool).exists() and not which(tool):
            self.skipTest("mica-dis not built")
        blob = self.asm(
            ".arch mica32\nldpi.b x4,[x2]\nstpi.b x4,[x1]\ndbnz x3, 0\nwfi\n",
            ["--flow"],
        )
        path = Path(self.tmp.name) / "test.bin"
        p = subprocess.run([tool, str(path)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("ldpi.b x4,[x2]", p.stdout)
        self.assertIn("stpi.b x4,[x1]", p.stdout)
        self.assertIn("dbnz x3,0x0", p.stdout)

    def test_wfi_stops_before_following_instruction(self):
        regs, _ = self.runsource(".arch mica32\nli8 x1,42\nwfi\nli8 x1,0\n")
        self.assertEqual(regs[1],42)

    def test_old_v01_encodings(self):
        old = Path("/mnt/data/mica32/assembler.py")
        if not old.exists():
            self.skipTest("previous SDK not available")
        spec = importlib.util.spec_from_file_location("mica_old", old)
        mod = importlib.util.module_from_spec(spec)
        import sys

        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        candidates = [
            ("li8 x1, 3\nadd x1,x1\nwfi\n", ()),
            ("movhi x2,0x1234\nmovlo x2,0xffff\n", ()),
            ("add3 x1,x2,x3\n", ()),
            ("vadd.u8 v0,v1,v2\n", ("--simd",)),
            ("lr.w x1,[x2]\n", ("--atomic",)),
        ]
        for source, opts in candidates:
            new = self.asm(source, opts)
            oldbytes, _ = mod.Assembler(
                simd="--simd" in opts, atomic="--atomic" in opts
            ).assemble(source)
            self.assertEqual(new, oldbytes, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
