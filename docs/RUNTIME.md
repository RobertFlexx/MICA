# Assembly runtime

The runtime provides callable assembly routines for memory, strings, arithmetic,
checksums and device output. Sources are in `stdlib/`; startup and linked-library
entry points are in `runtime/startup/`. Most routines use x1..x3 for arguments,
return a result in x1, clobber x2..x4 and preserve x5. Each source header lists its
exact interface. The [assembly ABI](architecture/ABI.md) defines the shared calling
convention.

Include a library after a halt or jump, so execution does not fall through into its
first routine. Include each module once: internal labels are global in a flat image.
Separate ELF objects support local symbol scope; export callable labels with
`.global`, as `runtime/startup/library32.mica` demonstrates.

## Modules

| Source in `stdlib/` | Main routines | Target |
| --- | --- | --- |
| `string.mica` | Copy, move, set, compare, length and other string helpers | 32/64-bit base |
| `strings_extra.mica` | `mica_memchr`, `mica_memrchr`, `mica_strncmp`, `mica_memswap` | 32/64-bit base |
| `flow.mica` | `mica_memcpy_flow`, `mica_memset_flow`, `mica_memcpy_words_flow` | F |
| `math32.mica`, `math64.mica` | Unsigned quotient/remainder, popcount, leading zero count | Matching XLEN |
| `arena32.mica`, `arena64.mica` | `mica_arena_init`, `mica_arena_alloc` | Matching XLEN |
| `checksum32.mica` | `mica_crc32` | 32-bit base |
| `ctype.mica` | ASCII classification and case conversion | Base |
| `console32.mica`, `console64.mica` | MMIO output and hexadecimal formatting | Matching XLEN |
| `atomic32.mica`, `atomic64.mica` | Exchange/addition and fenced synchronization helpers | A, emulator |
| `bits_hw.mica` | Popcount, leading/trailing zero count, byte swap | B |
| `buffer.mica` | XOR, full-length equality, zeroing | Base |
| `reduce.mica` | Byte sum and XOR; F sum variant | Base or F |
| `dsp32.mica` | Signed 16-bit dot product | 32-bit M |
| `dsp32_flow.mica` | `mica_dot_s16_flow`, signed streaming dot product | 32-bit 2.0 development r2+, M and F |
| `bounded32.mica` | Copy after source/destination range checks | 32-bit F |
| `macro.mica` | Compile-time helpers | Assembler source |

## Startup and linking

`runtime/startup/ram_start32.mica` sets the stack for a 64 KiB image, clears the
application's `bss_begin..bss_end` range, calls `main` and halts on return.
Initialized data already occupies its run address in the SRAM image. A separate
ROM-to-RAM copy stage is still needed for that memory layout.

The [linked example](toolchain/LINKER.md) combines startup, application and library
objects, checks CRC-32 and prints through UART. Its memory size and stack match
`runtime/startup/ram.ld`.

## CRC-32

`mica_crc32` takes x1=buffer and x2=byte count, returning CRC-32 in x1 and
preserving x5. It uses initial state 0xffffffff, reflected polynomial 0xedb88320,
least-significant-bit-first input and a final complement. ASCII `123456789` produces
0xcbf43926. The implementation is bitwise and uses no lookup table. The separate
[VHDL engine](hardware/PERIPHERALS.md#vhdl-crc-engine) exposes the same CRC through
MMIO.

## Copy and fill

`mica_memcpy_flow` takes x1=destination, x2=source and x3=byte count.
`mica_memset_flow` takes x1=destination, x2=fill byte and x3=byte count. Both return
the original destination in x1 and preserve x5. `mica_memcpy_words_flow` counts
32-bit words and requires four-byte-aligned pointers. Copies require nonoverlapping
ranges; `mica_memmove` handles overlap. The flow helpers check zero count before
`dbnz` to avoid decrementing zero into a full-width wrapped loop count.

`mica_memcpy_bounded` checks two end-exclusive ranges and addition overflow before
calling the F copy routine. Its fifth argument is passed in x5, which it preserves.
Valid copies can be interrupted partway through, and earlier stores remain after a
later fault. See the source for the exact register assignment and [bounds
experiment](research/DESIGN_EXPERIMENTS.md#buffer-bounds-in-software) for its
intended use.

## Fixed arena

`mica_arena_init` takes a 16-byte-aligned base in x1 and capacity in x2, then stores
a cursor and limit in global words. `mica_arena_alloc` rounds requests up to 16
bytes, returns the current cursor and advances it on success. Capacity or arithmetic
overflow returns zero without advancing the cursor. There is one global arena, with
no free operation or internal lock; callers serialize access.

## Buffer and numerical helpers

`mica_memxor(dst,src,count)` accepts disjoint ranges or identical pointers.
`mica_memeq_full(a,b,count)` reads the full requested length and returns one for
equal buffers, zero otherwise. Its instruction path has no data-dependent early
exit; timing still depends on the memory system. `mica_memzero` emits explicit byte
stores. These helpers preserve x5/x6 and return results through x1.

`mica_sum8`, `mica_xor8` and `mica_sum8_f` take x1=buffer and x2=count. They treat
bytes as unsigned, return the reduction in x1 and clobber x1..x4. The sum wraps at
XLEN; the empty case returns zero without dereferencing the pointer. The F variant
uses post-increment and `dbnz`. `examples/reduce32.mica` exercises it.

`dsp32.mica` computes signed 16-bit dot products with results wrapping at 32 bits.
`examples/fir32.mica` produces 16, 8, -32 and 40; tests compare those samples with
an independent Python convolution. The B helpers `mica_popcount_b`, `mica_clz_b`,
`mica_ctz_b` and `mica_bswap_b` take and return x1 without changing the other
caller-saved registers.

## C interfaces

`include/mica.h` contains prospective C-compatible declarations. The current runtime
is used through the assembly ABI; a compiler backend, complete language ABI and
tested headers/library subset are still needed for a freestanding C environment.
Hosted facilities such as files, locale and threads would also need an
operating-system model.
