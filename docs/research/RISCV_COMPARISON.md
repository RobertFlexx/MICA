# MICA 2.0 advantages over RISC-V

MICA's clearest demonstrated advantage is **denser counted loops**. A short
decrement-and-branch occupies two bytes. With F enabled, a load or store can
also advance its pointer in two bytes. Together, those features encode a
byte-copy loop in six bytes and three instructions.

## Assembled results

`benchmarks/riscv_density.py` assembles the same operations with MICA's assembler
and LLVM's RISC-V assembler. RISC-V uses a0..a3, within the compressed register
subset. The Zcb configuration is enabled explicitly, allowing compressed byte
loads and stores. No linker padding, startup, exit code or data is counted.

| Loop or operation | MICA 2.0 bytes | RV32I bytes | RV32IC bytes | RV32IC + Zcb bytes |
| --- | ---: | ---: | ---: | ---: |
| Decrement and conditional branch | 2 | 8 | 4 | 4 |
| Byte-copy body | 6 | 24 | 16 | 12 |
| Word-copy body | 6 | 24 | 12 | 12 |
| Stack save and restore | 4 | 8 | 4 | 4 |

For the byte-copy body, MICA is **62.5% smaller than RV32IC** and **50% smaller
than RV32IC + Zcb**. For the word-copy body it is **50% smaller than either
compressed configuration**. The fused branch itself saves 50%. These are
kernel-specific encoding results, not average application reductions.

MICA's byte-copy body:

```asm
.arch mica32v2
loop:
    ldpi.b x4,[x2]
    stpi.b x4,[x1]
    dbnz.s x3,loop
```

Assemble this snippet with `--mica2 --flow`. Its RISC-V counterpart is:

```riscv
loop:
    lbu  a3,0(a1)
    sb   a3,0(a0)
    addi a0,a0,1
    addi a1,a1,1
    addi a2,a2,-1
    bnez a2,loop
```

The loop is entered with a positive element count and valid, naturally aligned
buffers. MICA F and 2C are enabled. Under those preconditions, both versions
perform one load, one store, two pointer advances and one counter decrement per
element. Three versus six retired instructions is an architectural instruction
count; it does not establish a twofold cycle or throughput improvement.

## Register budget

MICA-2C defines eight register slots, including hardwired zero, link and stack.
[RV32E defines sixteen](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32e.html);
RV32I defines thirty-two. MICA therefore has half RV32E's architectural slots.
This is a smaller storage budget, with fewer general-purpose temporaries.
Physical area depends on port count, implementation and synthesis; spills can
erase a code-size advantage. MICA-2E offers sixteen slots when that tradeoff is
preferable. No compiler-generated workload comparison is available yet.

## Where RISC-V matches or exceeds this result

The [RISC-V C specification](https://docs.riscv.org/reference/isa/v20260120/unpriv/c-st-ext.html)
already provides compact SP-relative word accesses, and RV64C provides compact
doubleword stack accesses. The four-byte save/restore case ties MICA. RISC-V's
SP-relative reach is substantially larger than MICA's eight full-width slots.
MICA's stack forms are not a unique advantage over compressed RISC-V.

The [Zc specification](https://docs.riscv.org/reference/isa/unpriv/zc.html)
adds compressed byte/halfword accesses and multi-register stack operations.
This experiment enables Zcb for byte accesses; it does not measure Zcmp
prologues or Zcmt dispatch tables. Custom RISC-V post-increment and hardware-loop
extensions, such as [CORE-V](https://docs.openhwgroup.org/projects/cv32e40p-user-manual/en/cv32e40p_v1.7.2/instruction_set_extensions.html),
also require their own comparison. The results apply to the named standard
profiles, not every processor using RISC-V.

## Reproduce and interpret

```sh
python3 benchmarks/riscv_density.py --assembler build/mica-as --emulator build/mica-run
```

The [archived JSON](../engineering/results/mica2/riscv-density.json) contains
each source, byte count and RISC-V encoding. Complete MICA byte/word copy
programs execute in the emulator at both XLENs, and the MICA 2.0 retirement suite
compares F copy execution against RTL. RISC-V is assembled and sized in this
experiment; it is not independently executed here.

The next hardware comparison must map both CPUs with the same memory, peripherals,
extensions, clock constraints and tool flow, then measure complete workloads.
**MICA currently has evidence for these encoding advantages; lower power and
higher clock speed remain unmeasured.**
