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

Object fragments are placed in command-line order, each aligned to at least 16
bytes and to its largest `.align` requirement. Padding depends on the absolute
address, including when `--base` is nonzero. The first object's `_start` must
therefore lead the reset image for hardware. The default origin is 0.
`--base N` sets another aligned origin; the ELF loader honors it while
raw binaries still require a platform loader at that origin. `--entry` selects an
exported symbol; otherwise `_start` is preferred. The fallback is the first
object's start after alignment padding. Entry must be even and inside the image.

The small MICA image script accepts only `ORIGIN = number;`, `LENGTH = number;` and
`ENTRY = symbol;`, one per line, with # comments. This is not GNU ld script syntax.
The supplied script sets 64 KiB at 0 and entry `_start`. Length overflow, undefined
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
shows the revision and its required features.

## Compact counted loops in objects

`dbnz.s counter,target` accepts local and exported targets in separately assembled
MICA 2.0 objects. `PCREL6` retains the two-byte encoding and checks the signed
six-bit halfword range after placement. The counter must be x1..x7. Alignment
padding between objects counts toward the distance; choose the long `dbnz` form
with F when the target can be farther away.

```asm
.arch mica32v2
.global _start
_start: li8 x1,0
li8 x2,7
loop: addi x1,6
dbnz.s x2,loop
stop
```

Save as `counted.mica`, assemble with `mica-as --mica2 -c counted.mica -o counted.o`,
then link with `mica-ld counted.o -o counted.bin --elf counted.elf`. Running
`mica-run --mica2 counted.elf` reports `x1=0x2a`. The loop needs no F extension.
