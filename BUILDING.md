# Building and verifying MICA 1.0

CMake 3.20+, a GCC or Clang compiler accepting C++23, and Python 3.10+ are
required. The vector reference uses the compilers' `__int128` extension. Linux
is tested locally; macOS is configured in CI and remains pending execution there.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
cmake --install build --prefix "$PWD/build/install"
```

Use the executables from this build. `bin/linux-x86_64` contains historical
convenience binaries and is not updated by a source build.

```sh
cmake -S . -B build-san -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE=Debug   -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'   -DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address,undefined' -DMICA_FUZZ=ON
cmake --build build-san --parallel 4
ctest --test-dir build-san --output-on-failure
```

On Solus with Homebrew Clang, Clang may need `--gcc-install-dir` pointing at
the directory containing `gcc -print-file-name=crtbeginS.o`. This is a host
compiler installation issue. LeakSanitizer needs process-inspection access;
run in an environment permitting it. ASan/UBSan failures are not suppressed.

HDL validation uses Icarus/vvp, Verilator, Yosys, GHDL, SBY, Z3 and Graphviz.
The locally tested bundle is OSS CAD Suite **2026-10-17**, Linux x86-64. CI
pins that release; no script downloads dependencies during verification.
Put the bundle's `bin` directory on PATH. GNU make is also needed.

```sh
make -C rtl sim32 sim64 sim-flow32 sim-flow64 sim-bits32 sim-bits64 sim-trap sim-trap-irq
make -C rtl sim-sram sim-sram-txn sim-watchdog sim-watchdog-soc sim-firmware sim-scheduler sim-add64 sim-peripherals
python3 scripts/build_rtl_sim.py --xlen 32
python3 scripts/build_rtl_sim.py --xlen 64
python3 verification/differential/run.py --tools build
python3 scripts/run_formal.py
python3 scripts/synthesize.py --tools build
python3 scripts/generate_schematics.py --check
```

The makefiles expect `../build/mica-as`; override `ASM` for another build.
Verilator and SBY invoke shell/make commands that do not support spaces in
build paths. Their Python runners stage builds in temporary directories and
copy results into `build`. Source paths containing spaces are supported.

For fetch experiments also build with `--reuse 0` for each XLEN, then run
`python3 benchmarks/hardware.py --tools build`. Run
`python3 benchmarks/alu_activity.py` for ALU synthesis and switching activity.
All generated simulation files are build artifacts. Vivado and a physical
board are separate requirements described in the FPGA guide.

Create a binary SDK archive with `cpack --config build/CPackConfig.cmake -B
build/releases -G TGZ`. The source archive is separate:
`python3 scripts/package_source.py --update-checksums`. Review the source file
list before updating checksums. Its tar metadata and gzip header are fixed so
identical source contents produce an identical archive. Neither archive includes
local build junk. Existing prebuilt Linux executables in the source tree remain
historical fixtures; build current tools or use the binary SDK archive.

For a single logged regression command, run `python3 scripts/verify.py --all`.
Without --all it builds and runs the software suite. Missing HDL tools fail
explicitly when --all is requested.
