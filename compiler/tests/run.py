#!/usr/bin/env python3
"""Compile C to MICA objects, link, execute and compare with native Clang."""

import argparse
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--host-cc", default="cc")
    parser.add_argument("--output", type=Path, default=ROOT / "build/compiler")
    parser.add_argument("--rtl", type=Path)
    args = parser.parse_args()
    args.tools = args.tools.resolve()
    args.output.mkdir(parents=True, exist_ok=True)

    def run(command, ok=True):
        result = subprocess.run([str(x) for x in command], capture_output=True, text=True, timeout=60)
        if (result.returncode == 0) != ok:
            raise AssertionError(f"{command}\n{result.stdout}{result.stderr}")
        return result

    # The host wrapper prints all 32 return bits, avoiding exit-code truncation.
    host = args.output / "host.c"
    host.write_text('#include <stdio.h>\nint mica_test_main(void);\n'
                    'int main(void) { printf("%u\\n", (unsigned)mica_test_main()); }\n')
    cases = [("multifile", [ROOT / "compiler/tests/program.c", ROOT / "compiler/tests/library.c"])]
    rng = random.Random(0xC32)
    for index in range(12):
        source = args.output / f"random{index}.c"
        a, b, c = [rng.randrange(1, 100000) for _ in range(3)]
        source.write_text(f"unsigned int main(void) {{ unsigned int x={a}u, y={b}u;\n"
                          f"for (unsigned int i=0; i<7; ++i) {{ x=(x*{c}u)^y; y=(y<<3)|(y>>29); }}\n"
                          "if (x < y) { x += y; } else { x -= y; } return x; }\n")
        cases.append((source.stem, [source]))
    results = []
    for name, sources in cases:
        native = (args.output / (name + ".host")).resolve()
        run([args.host_cc, "-Dmain=mica_test_main", "-c", sources[0], "-o", args.output / "host-main.o"])
        run([args.host_cc, host, args.output / "host-main.o", *sources[1:], "-o", native])
        expected = int(run([native]).stdout)
        for profile in ("MICA-2C", "MICA-2E"):
            objects = []
            for index, source in enumerate(sources):
                obj = args.output / f"{name}-{profile}-{index}.o"
                run([sys.executable, ROOT / "compiler/mica_cc.py", "--clang", args.clang,
                     "--profile", profile, "--assembler", args.tools / "mica-as", source, "-o", obj])
                objects.append(obj)
            startup = args.output / "start.mica"
            startup.write_text(".arch mica32v2\n.global _start\n.extern main\n_start:\n"
                               "li32 sp,65520\nli8 x5,77\ncall main\nstop\n")
            start = args.output / "start.o"
            run([args.tools / "mica-as", "--profile", profile, "-c", startup, "-o", start])
            elf = args.output / f"{name}-{profile}.elf"
            binary = args.output / f"{name}-{profile}.bin"
            run([args.tools / "mica-ld", start, *objects, "--elf", elf, "-o", binary])
            trace = args.output / f"{name}-{profile}.jsonl"
            for engine in ([], ["--fast"], ["--native-loops"]):
                result = run([args.tools / "mica-run", "--profile", profile, *engine,
                              "--memory", 65536, "--steps", 200000, "--retire-trace", trace, elf])
                events = list(map(json.loads, trace.read_text().splitlines()))
                regs = events[-1]["regs"]
                if (regs[1], regs[5], regs[7]) != (expected, 77, 65520):
                    raise AssertionError(f"{name}/{profile}: incorrect result or ABI preservation: {result.stderr}")
            if args.rtl:
                sys.path.insert(0, str(ROOT / "verification/differential"))
                from run import compare
                driver = args.rtl / f"{profile}-reuse1/Vmica_core_txn"
                actual = args.output / f"{name}-{profile}.rtl.jsonl"
                for seed in (1, 17, 1234):
                    run([driver, binary, actual, seed])
                    compare(trace, actual, f"C/{name}/{profile}/{seed}")
            results.append({"name": name, "profile": profile, "expected": expected,
                            "rom_bytes": binary.stat().st_size, "retired": len(events),
                            "rtl": bool(args.rtl)})
            print("PASS C", name, profile, flush=True)
    with tempfile.TemporaryDirectory() as temp:
        source, obj = Path(temp) / "unsupported.c", Path(temp) / "keep.o"
        for text in ("double main(void) { return 1.0; }",
                     "int main(int x) { return 99 / x; }",
                     "int main(void) { int a[4]={1,2,3,4}; return a[0]; }"):
            source.write_text(text)
            obj.write_bytes(b"previous object")
            result = run([sys.executable, ROOT / "compiler/mica_cc.py", "--clang", args.clang,
                          source, "-o", obj], ok=False)
            if "unsupported" not in result.stderr or obj.read_bytes() != b"previous object":
                raise AssertionError("unsupported input must fail without replacing output")
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"PASS {len(results)} C/profile cases, native oracle, ABI, three execution engines and negative diagnostics")


if __name__ == "__main__":
    main()
