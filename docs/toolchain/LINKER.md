# Linking assembly files

```sh
build/mica-as -c runtime/startup/ram_start32.mica -o start.o
build/mica-as -c firmware/examples/multifile_main.mica -o main.o
build/mica-as -c runtime/startup/library32.mica -o library.o
build/mica-ld start.o main.o library.o -T runtime/startup/ram.ld   -o firmware.bin --elf firmware.elf --map firmware.map
build/mica-objdump main.o
build/mica-nm firmware.elf
build/mica-run firmware.elf
build/mica-objcopy -O ihex firmware.elf firmware.hex
```

Object fragments are placed in command-line order, each aligned to 16 bytes. The
first object's `_start` must therefore lead the reset image for hardware. Default
origin is 0. `--base N` sets another aligned origin; the ELF loader honors it while
raw binaries still require a platform loader at that origin. `--entry` selects an
exported symbol; otherwise `_start` is preferred and origin is used if no such
global exists. Entry must be even and inside the image.

The small MICA image script accepts only `ORIGIN = number;`, `LENGTH = number;` and
`ENTRY = symbol;`, one per line, with # comments. This is not GNU ld script syntax.
The supplied script sets64KiB at 0 and entry `_start`. Length overflow, undefined
referenced strong symbols, mixed XLEN, duplicate definitions, invalid patch
templates and displacement overflow fail before creating output files. Relocation
semantics and section restrictions are in OBJECT_FORMAT.md.

## MICA 2.0 PC-relative symbols

`adrpc` uses the instruction's own PC as the relocation base. For nearby
symbols, `ADRPC16` supplies a signed 16-bit *halfword* displacement and preserves
the original destination register. The range is -65536 to +65534 bytes;
unrepresentable or odd-byte target distances are link errors.

The 32- and 64-bit examples in `firmware/examples/mica2_pcrel_*` reference data
from a different object, load the value 41 and return 42 in `x1`:

```sh
for width in 32 64; do
  build/mica-as --mica2 --xlen "$width" -c \
    "firmware/examples/mica2_pcrel_main${width}.mica" -o main.o
  build/mica-as --mica2 --xlen "$width" -c \
    "firmware/examples/mica2_pcrel_data${width}.mica" -o data.o
  build/mica-ld main.o data.o --base 0x1000 -o image.bin --elf image.elf
  build/mica-objdump image.elf
  build/mica-run --mica2 --xlen "$width" image.elf
done
```

The ELF reader enforces matching ISA 1.0/2.0 modes and required extension bits.
A legacy object and a 2.0 object cannot share an executable. `mica-objdump`
shows the revision and its required features; this does not imply a generic
ELF ABI or a complete C compiler backend.
