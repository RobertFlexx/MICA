# Building MICA

The software builds with CMake 3.20+, Python 3.10+, and GCC or Clang accepting
C++23. The vector interpreter also uses the compilers' `__int128` extension.
MICA 3.0 development validation uses Linux. Historical Linux/macOS results are in the
[1.0 CI archive](docs/engineering/results/ci.json).

## Software

From the repository root:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
cmake --install build --prefix "$PWD/build/install"
```

The seven tools are written to `build/`. The install tree also contains the
assembly libraries, startup code, examples, headers and documentation.
`bin/linux-x86_64` holds the historical binaries used for compatibility work;
source builds leave those files alone.
CTest uses the Python interpreter selected by CMake; `Python3_EXECUTABLE` can
select a particular installation. Repository file discovery needs no ripgrep,
and extracted source archives can run their tests without Git.

### Sanitizers and fuzzing

```sh
cmake -S . -B build-san \
  -DCMAKE_CXX_COMPILER=clang++ \
  -DCMAKE_BUILD_TYPE=Debug \
  -DMICA_FUZZ=ON \
  -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' \
  -DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address,undefined'
cmake --build build-san --parallel 4
ctest --test-dir build-san --output-on-failure
```

`MICA_FUZZ` enables the Clang libFuzzer target and a seeded 10,000-run test.
LeakSanitizer needs permission to inspect processes. A restricted container can
prevent it from starting; use an environment that permits that access.

On Solus, Homebrew Clang may need `--gcc-install-dir` pointing to the directory
that contains `gcc -print-file-name=crtbeginS.o`. This selects the installed GCC
runtime and is specific to that host setup.

## HDL simulation and synthesis

The open-source flow uses Icarus Verilog/vvp, Verilator, GHDL, Yosys, SBY, Z3,
Graphviz and GNU make. The recorded r2 runs use OSS CAD Suite **2026-10-17** on
Linux x86-64, also pinned in CI. Install the bundle separately and put its `bin`
directory on `PATH` before running the commands below.

Drawing regeneration also needs qpdf. PDF timestamps and document IDs are
normalized; identical RTL, generator sources, tools and fonts produce identical
collection artifacts. CI checks committed artifact hashes without rerendering.

```sh
make -C rtl sim32 sim64 sim-mica2-32 sim-mica2-64 sim-mica2-timer32 sim-mica2-timer64
make -C rtl sim-flow32 sim-flow64 sim-bits32 sim-bits64 sim-trap sim-trap-irq
make -C rtl sim-sram sim-sram-txn sim-watchdog sim-watchdog-soc sim-firmware sim-scheduler sim-add64 sim-peripherals
python3 scripts/build_rtl_sim.py --xlen 32
python3 scripts/build_rtl_sim.py --xlen 64
python3 verification/differential/run.py --tools build
python3 scripts/build_rtl_sim.py --profile MICA-2C
python3 scripts/build_rtl_sim.py --profile MICA-2E
python3 scripts/build_rtl_sim.py --profile MICA-2L
python3 verification/differential/mica2.py --tools build
python3 scripts/run_formal.py
python3 scripts/synthesize.py --tools build
python3 scripts/generate_schematics.py --check
python3 scripts/generate_soc_schematic.py --check
python3 scripts/generate_mica2_diagrams.py --check
python3 scripts/generate_overview_schematics.py --check
python3 scripts/generate_v3_schematics.py --check
```

The makefiles expect `../build/mica-as`. For another build directory, pass its
assembler path as a quoted `ASM` argument. `sim-peripherals` runs the native
Verilog/VHDL blocks, the converted CRC engine, both word-size SoCs and the actual
Arty board top. Logs and waveforms are written under `build/peripherals`.

The Verilator and SBY runners support repository paths containing spaces by
staging builds in temporary paths without spaces and copying results into `build`.

For the fetch experiment, also build both word sizes with `--reuse 0`, then run
`python3 benchmarks/hardware.py --tools build`. The separate ALU experiment is
`python3 benchmarks/alu_activity.py`. See the [benchmark guide](docs/research/BENCHMARKS.md)
for the measured quantities and the [FPGA guide](docs/hardware/FPGA_BUILD.md) for
Vivado and board requirements.

## Run the complete local regression

```sh
python3 scripts/verify.py --all
```

This command builds the tools, runs the software and hardware suites, and saves
stage commands, logs and exit status under `build/verify/validation`. `--all`
requires every listed HDL tool. Without that option the runner executes the
software build and CTest suite only. `--build-dir` selects another output tree.
A new invocation clears the previous stage summary before checking dependencies,
so an unavailable tool cannot leave a previous successful run as current evidence.
The software stage also writes `validation/ctest.xml`.

## SDK archives

```sh
cpack --config build/CPackConfig.cmake -B build/releases -G TGZ
python3 scripts/package_source.py --update-checksums
```

The first command packages the installed tools and support files. The second
updates the source checksum manifest and writes a source archive. Its fixed tar
metadata and gzip header make the archive repeatable for identical source
contents. Review the included files before updating the manifest.

`scripts/check_release.py` extracts the binary SDK and tests the installed
tools, separate compilation under both ISA revisions, compact branch/address
relocations, object alignment, startup library and UART/CRC firmware. Supply
`--source` as well to verify source checksums and perform a clean build and CTest
run. See its `--help` for archive arguments. Build outputs stay under `build/`.
CI checks the source manifest before packaging and runs these extracted-source
checks in a separate release job. Build and sanitizer output directories are
excluded from the source archive.

## MICA 2.0 comparisons, drawings and evidence

LLVM's `llvm-mc` and `llvm-objcopy` are needed for the RISC-V code-size comparison.
The full runner executes it when both are available; the 2.0 evidence archiver
requires that stage. It assembles RV32I, RV32IC and RV32IC + Zcb loop bodies and
executes the complete MICA copy programs at both widths.

```sh
python3 benchmarks/riscv_density.py
python3 scripts/archive_mica2_evidence.py --build build/verify
```

To regenerate all drawings after RTL or generator changes:

```sh
python3 scripts/generate_schematics.py
python3 scripts/generate_soc_schematic.py
python3 scripts/generate_mica2_diagrams.py
python3 scripts/generate_overview_schematics.py
python3 scripts/generate_v3_schematics.py
```

The generators refresh their SHA-256 manifests of sources and previews.
See the [drawing index](docs/hardware/DATAPATH.md).

## Format sources

Install clang-format, Black and cmake-format, then run:

```sh
python3 scripts/format_code.py
python3 scripts/format_code.py --check
# To touch only reviewed files:
python3 scripts/format_code.py --path toolchain/assembler.cpp --path tests/elf_revision.py
```

C++/SystemVerilog/Verilog use `.clang-format`; Python uses `pyproject.toml`;
CMake uses `.cmake-format.yaml`. `--cmake-format PATH` selects a formatter
installed with a supported Python version. JSON uses two-space indentation.
The formatter stages every changed file in memory and does not write any
source if a format tool fails. It excludes assembly, VHDL, shell,
Tcl, constraints and other data-sensitive inputs untouched; trimming spaces
inside a shell here-document or YAML scalar can change behavior.
Generated tables and drawings retain their generator's canonical output.
Regenerate drawings and rerun verification after formatting RTL.
