#!/usr/bin/env python3
"""Compare accelerated execution against the always-available reference engine."""
import os
import random
import re
import subprocess
import tempfile
from pathlib import Path
import unittest

ASM = os.environ.get('MICA_AS', 'build/mica-as')
RUN = os.environ.get('MICA_RUN', 'build/mica-run')


class Engines(unittest.TestCase):
    def build(self, src, xlen=32, features=()):
        work = Path(self.tmp.name)
        (work / 'test.mica').write_text(src)
        flags = ['--xlen', str(xlen), *features]
        p = subprocess.run([ASM, *flags, str(work / 'test.mica'), '-o', str(work / 'test.bin')], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return work / 'test.bin', flags

    def run_machine(self, binary, flags, engine=(), steps=200000):
        p = subprocess.run([RUN, *flags, *engine, '--steps', str(steps), str(binary)], capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr

    def assert_same(self, binary, flags, steps=200000):
        baseline = self.run_machine(binary, flags, steps=steps)
        self.assertEqual(baseline[0], 0, baseline)
        for engine in [('--fast',), ('--native-loops',)]:
            other = self.run_machine(binary, flags, engine, steps)
            self.assertEqual(baseline, other, engine)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_random_scalar_programs(self):
        rng = random.Random(0xBADC0DE)
        ops = ['add', 'sub', 'xor', 'and', 'or', 'sltu', 'seq', 'mov']
        for width in (32, 64):
            for _ in range(25):
                lines = [f'.arch mica{width}', 'li8 x1,24', 'li8 x2,7', 'li8 x3,0']
                for _ in range(35):
                    op = rng.choice(ops)
                    d, s = rng.randrange(1, 6), rng.randrange(1, 6)
                    lines.append(f'{op} x{d},x{s}')
                    lines.append(f'addi x{d},{rng.randint(-32, 32)}')
                lines.append('wfi')
                self.assert_same(*self.build('\n'.join(lines), width))

    def test_counted_loop(self):
        for width in (32, 64):
            for count in (1, 2, 13, 999, 4096):
                source = f'.arch mica{width}\nli32 x2,{count}\nli8 x1,97\nloop:\naddi x1,-17\ndbnz x2,loop\nwfi\n'
                self.assert_same(*self.build(source, width, ['--flow']), steps=2*count + 20)

    def test_fallback_memory_and_extension(self):
        for width in (32, 64):
            code = f".arch mica{width}\nli32 x2,256\nli8 x1,93\nstb x1,[x2]\nldb x3,[x2]\nwfi\n"
            self.assert_same(*self.build(code, width))
            code = f".arch mica{width}\nli8 x1,17\npopcnt3 x3,x1\nwfi\n"
            self.assert_same(*self.build(code, width, ['--bitops']))
            code = f".arch mica{width}\nli32 x2,256\nli8 x1,41\nstpi.b x1,[x2]\nwfi\n"
            self.assert_same(*self.build(code, width, ['--flow']))

    def test_runtime_reduction(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'examples/reduce32.mica').read_text()
        source = source.replace('.include "../stdlib/reduce.mica"',
                                '.include "' + str(root / 'stdlib/reduce.mica') + '"')
        binary, flags = self.build(source, 32, ['--flow'])
        state = self.run_machine(binary, flags, ('--native-loops',))
        self.assertEqual(state[0], 0, state[2])
        self.assertIn('x1=0x15', state[2])
        self.assert_same(binary, flags)

    def test_assembler_contracts(self):
        binpath, _ = self.build('.arch mica32\nstart:\nli8 x1,5\n.assert 1\nwfi\n')
        self.assertTrue(binpath.exists())
        for source in ['.error "broken"\n', '.assert 0,"wrong"\n']:
            path = Path(self.tmp.name)/'invalid.mica'
            path.write_text(source)
            p = subprocess.run([ASM, str(path), '-o', str(path.with_suffix('.bin'))],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0,source)
        one=Path(self.tmp.name)/'a.mica'
        two=Path(self.tmp.name)/'b.mica'
        one.write_text('.include "b.mica"\n')
        two.write_text('.include "a.mica"\n')
        p=subprocess.run([ASM, str(one)],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('recursive include',p.stderr)
        good=Path(self.tmp.name)/'good.mica'
        good.write_text('entry:\nli8 x1,1\nwfi\n')
        args=[ASM,str(good),'-o',str(Path(self.tmp.name)/'good.bin'),'--map',str(Path(self.tmp.name)/'good.map')]
        p=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('entry', (Path(self.tmp.name)/'good.map').read_text())

if __name__ == '__main__':
    unittest.main()
