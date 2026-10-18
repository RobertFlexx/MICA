# Building MICA

The software builds with CMake 3.20+, Python 3.10+, and GCC or Clang accepting
C++23. The vector interpreter also uses the compilers' `__int128` extension.
Local results use Linux; GCC/Clang Linux and Clang macOS builds also pass the
[recorded CI run](docs/engineering/results/ci.json).

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

```sh
make -C rtl sim32 sim64 sim-flow32 sim-flow64 sim-bits32 sim-bits64 sim-trap sim-trap-irq
make -C rtl sim-sram sim-sram-txn sim-watchdog sim-watchdog-soc sim-firmware sim-scheduler sim-add64 sim-peripherals
python3 scripts/build_rtl_sim.py --xlen 32
python3 scripts/build_rtl_sim.py --xlen 64
python3 verification/differential/run.py --tools build
python3 scripts/run_formal.py
python3 scripts/synthesize.py --tools build
python3 scripts/generate_schematics.py --check
python3 scripts/generate_soc_schematic.py --check
```

The makefiles expect `../build/mica-as`. For another build directory, pass its
assembler path as a quoted `ASM` argument. `sim-peripherals` runs the native
Verilog/VHDL blocks, the converted CRC engine, both word-size SoCs and the actual
Arty board top. Logs and waveforms are written under `build/peripherals`.

Spaces in directory names are legal. Some HDL build tools need reminding.
The Verilator and SBY runners stage their generated builds in temporary paths
without spaces, then copy the results back into `build`.

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
tools, separate compilation, startup library and UART/CRC firmware. Supply
`--source` as well to verify source checksums and perform a clean build and CTest
run. See its `--help` for archive arguments. Build outputs stay under `build/`.
