#!/usr/bin/env python3
"""Compare saved and current cores on identical firmware and a signed DSP kernel."""

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification/differential"))
from run import checked, compare

FLAGS = ["--mica2", "--xreg", "--mul", "--flow", "--bitops", "--trap"]
SEEDS = (1, 17, 1234, 5678, 99)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, default=ROOT / "build")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--rtl", type=Path, default=ROOT / "build/rtl")
    parser.add_argument("--output", type=Path, default=ROOT / "build/core-revision")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []

    def measure(name, width, text, expected, drivers, kernel=None):
        stem = args.output / name
        source, binary, symbols, reference = [Path(str(stem) + ext) for ext in
                                              (".mica", ".bin", ".map", ".ref.jsonl")]
        source.write_text(text)
        flags = [*FLAGS, "--xlen", width]
        checked([args.tools / "mica-as", *flags, source, "-o", binary, "--map", symbols])
        checked([args.tools / "mica-run", *flags, "--memory", 65536,
                 "--retire-trace", reference, binary])
        events = list(map(json.loads, reference.read_text().splitlines()))
        if events[-1]["regs"][1] != expected:
            raise AssertionError(f"incorrect independent result: {name}")
        addresses = {line.split()[1]: int(line.split()[0], 16)
                     for line in symbols.read_text().splitlines()}
        for version, path in drivers:
            driver = path / f"MICA-2{'E' if width == 32 else 'L'}-reuse1/Vmica_core_txn"
            runs = []
            for seed in SEEDS:
                trace = Path(str(stem) + f".{version}-{seed}.jsonl")
                output = checked([driver, binary, trace, seed])
                compare(reference, trace, f"{name}/{version}/{seed}")
                runs.append(json.loads(output.stderr))
            row = {"name": name, "xlen": width, "core": version,
                   "driver_sha256": hashlib.sha256(driver.read_bytes()).hexdigest(),
                   "rom_bytes": binary.stat().st_size, "retired": sum(e["retired"] for e in events),
                   "median_cycles": statistics.median(r["cycles"] for r in runs),
                   "fetches": runs[0]["fetches"], "data_requests": runs[0]["loads"] + runs[0]["stores"],
                   "runs": runs}
            if kernel:
                row["kernel_bytes"] = addresses[kernel + "_done"] - addresses[kernel + "_loop"]
            results.append(row)
            print(name, version, row["median_cycles"], "cycles,", row["fetches"], "fetches", flush=True)

    for stem, width, expected in [("arithmetic32", 32, 42),
                                 ("arithmetic64", 64, 0x0123456889ABCDEE),
                                 ("flow_copy32", 32, 3), ("string32", 32, 4),
                                 ("div32", 32, 858993459)]:
        code = (ROOT / "examples" / (stem + ".mica")).read_text().replace("wfi", "stop")
        code = re.sub(r'\.include "([^"]+)"',
                      lambda m: '.include "' + str((ROOT / "examples" / m[1]).resolve()) + '"', code)
        measure(stem, width, code, expected, [("baseline", args.baseline), ("current", args.rtl)])
    # Independent integer arithmetic supplies the oracle for both kernel versions.
    left, right = [-3, 32767, -32768, 17] * 16, [19, -5, -7, 123] * 16
    expected = sum(a * b for a, b in zip(left, right)) & 0xffffffff
    for flow in (False, True):
        suffix = "_flow" if flow else ""
        routine = "mica_dot_s16" + suffix
        code = (".arch mica32v2\nli32 x1,left\nli32 x2,right\nli8 x3,64\n"
                f"call {routine}\nstop\n"
                + (ROOT / f"stdlib/dsp32{suffix}.mica").read_text()
                + "\n.align 2\nleft: .half " + ",".join(map(str, left))
                + "\nright: .half " + ",".join(map(str, right)) + "\n")
        measure("dot-s16" + suffix, 32, code, expected, [("current", args.rtl)], "dot_s16" + suffix)
    report = {"method": "Same assembled firmware and five fixed bus-stall seeds; architectural retirement compared to the interpreter on every run. DSP variants use the same signed input and independent host sum.",
              "limits": "Handwritten kernels; cycles and memory requests only. No compiler, routed timing, power or energy claim.",
              "results": results}
    (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
