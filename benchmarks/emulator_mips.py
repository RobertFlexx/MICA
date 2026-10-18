#!/usr/bin/env python3
"""Interpreter and counted-loop translator microbenchmark, not a CPU benchmark."""
import argparse
import json
import os
import re
import statistics
import subprocess
import tempfile
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--assembler', default=os.environ.get('MICA_AS', 'build/mica-as'))
    ap.add_argument('--emulator', default=os.environ.get('MICA_RUN', 'build/mica-run'))
    ap.add_argument('--iterations', type=int, default=50_000_000)
    ap.add_argument('--repeats', type=int, default=5)
    ap.add_argument('--output', default=None)
    args = ap.parse_args()
    if args.iterations < 1 or args.iterations > 2_000_000_000 or args.repeats < 3:
        ap.error('use 1..2000000000 iterations and at least 3 repeats')
    result = {'microbenchmark': 'addi/dbnz counted loop, not general emulator throughput',
              'platform': os.uname().machine, 'host': os.uname().sysname + ' ' + os.uname().release, 'cpu_model': next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), 'unknown') if Path('/proc/cpuinfo').exists() else 'see host system profiler', 'iterations': args.iterations,
              'results': {}}
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / 'bench.mica'
        binary = Path(tmp) / 'bench.bin'
        for width in (32, 64):
            src.write_text(f'.arch mica{width}\nli32 x2,{args.iterations}\nloop:\naddi x1,1\ndbnz x2,loop\nwfi\n')
            subprocess.run([args.assembler, '--xlen', str(width), '--flow', str(src), '-o', str(binary)], check=True, capture_output=True)
            for name, opts in (('reference', []), ('fast', ['--fast']), ('native-counted-loop', ['--native-loops'])):
                times=[]
                for _ in range(args.repeats):
                    t0 = time.perf_counter()
                    p = subprocess.run([args.emulator,'--xlen',str(width),'--flow', *opts,
                                        '--steps',str(2*args.iterations+100),str(binary)], capture_output=True,text=True)
                    sec = time.perf_counter() - t0
                    if p.returncode:
                        raise RuntimeError(p.stderr)
                    retired = re.search(r'\bretired=(\d+)',p.stderr)
                    ret = int(retired.group(1)) if retired else -1
                    x1 = re.search(r'\bx1=0x([0-9a-f]+)',p.stderr)
                    if ret != 2 * args.iterations + 3 or not x1 or int(x1.group(1),16) != args.iterations % (1<<width):
                        raise RuntimeError('benchmark produced wrong machine state: '+p.stderr)
                    times.append(sec)
                median=statistics.median(times)
                result['results'][f'{width}/{name}'] = {
                    'median_seconds':round(median,6),
                    'mips':round((2*args.iterations+3)/median/1e6,1),
                    'runs_seconds':[round(t,6) for t in times]}
    print(json.dumps(result, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(result,indent=2)+'\n')

if __name__ == '__main__':
    main()
