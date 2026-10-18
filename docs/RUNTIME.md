# Freestanding runtime library

MICA has a small set of callable assembly routines, not a complete C standard library. You can include a module at the end of an assembly program after a halt or jump, call its exported labels, and run it in the MICA emulator. It supports XLEN32 and XLEN64 unless marked otherwise. Most routines expect x1..x3 arguments, return x1, may change x2..x4, and restore x5. Check the header on each module.

## File map

| Module | Symbols / purpose | Required options |
| --- | --- | --- |
| `string.mica` | `mica_memcpy`, `mica_memmove`, `mica_memset`, `mica_strlen`, `mica_strnlen`, `mica_strcpy`, `mica_memcmp`, `mica_strcmp`, and other string helpers | baseline 32/64 |
| `strings_extra.mica` | `mica_memchr`, `mica_memrchr`, `mica_strncmp`, `mica_memswap` | baseline 32/64 |
| `flow.mica` | `mica_memcpy_flow`, `mica_memset_flow`, `mica_memcpy_words_flow` | `--flow` |
| `math32.mica` | unsigned divide/modulo, popcount and leading zero count | XLEN32 |
| `math64.mica` | unsigned divide/modulo, popcount and leading zero count | XLEN64 |
| `arena32.mica`, `arena64.mica` | `mica_arena_init`, `mica_arena_alloc`, 16-byte aligned fixed arena | matching XLEN |
| `checksum32.mica` | `mica_crc32`, reflected CRC-32/ISO-HDLC | XLEN32 |
| `ctype.mica` | ASCII digit/case classification and case conversion | baseline |
| `console32.mica`, `console64.mica` | MMIO output and hex-format helpers | corresponding XLEN |
| `atomic32.mica`, `atomic64.mica` | AMO exchange/addition and fenced synchronization helpers | `--atomic` |
| `macro.mica` | compile-time macros, not callable procedures | baseline |

Library sources are meant to be included once. They use global labels internally. ELF objects and local symbol scoping are supported by mica-as -c and mica-ld. Export public labels with .global, as runtime/startup/library32.mica demonstrates. Including the same source twice will create duplicate labels.

## CRC-32

`mica_crc32` takes x1=byte buffer and x2=byte count and returns CRC32 in x1. It starts at 0xffffffff, processes each byte least-significant-bit first using reflected polynomial 0xedb88320, then complements the result. The known standard test vector `123456789` returns `0xcbf43926`. The current routine is bitwise rather than table-driven; it is meant for correctness and portability, not peak throughput. x5 is preserved.

## Flow copy and memset

`mica_memcpy_flow` takes x1=destination, x2=source, x3=count in bytes. `mica_memset_flow` takes x1=destination, x2=fill byte, x3=count. They return the original destination in x1, and x5 is preserved. `mica_memcpy_words_flow` treats x3 as a number of 32-bit words and needs four-byte-aligned pointers. These routines do not handle overlapping copy regions; use `mica_memmove` for overlap. Each tests zero count before entering `dbnz`, so a zero count will not wrap into an extremely long loop.

## What "standard library" will require next

A conforming freestanding C implementation needs a working C compiler and ABI, real linkable symbols, startup and a specified subset of ISO C headers/functions. `malloc`, `printf`, floating point, locale, file descriptors and TLS also need an allocation/OS model. The SDK's current `include/mica.h` is a **future-facing declaration file** for parts of the assembly runtime. It is not a certification or a GCC target.

ELF image objects, basic relocation tests, linking and initialized-SRAM startup are implemented in engineering r2. Compiler machine-code lowering, full language ABI and a tested freestanding C environment remain unfinished.

## Fixed arena allocator

`mica_arena_init` takes a 16-byte aligned base pointer in x1 and the capacity in bytes in x2. It stores a cursor and a limit in internal global words. `mica_arena_alloc` rounds its requested size up to 16, returns the current cursor, and advances on success. If a request would exceed the capacity or wrap arithmetic, it returns zero without advancing the cursor. There is no free operation, there is one arena globally, and no lock or stack guard. It is useful for early bring-up and deterministic buffers, not a drop-in replacement for hosted malloc.

## Additional assembly modules

`stdlib/bits_hw.mica` contains `mica_popcount_b`, `mica_clz_b`, `mica_ctz_b`, and `mica_bswap_b`. Pass `--bitops`. They take a scalar in x1 and return x1 without touching the ordinary caller-saved registers.

`stdlib/buffer.mica` contains `mica_memxor(dst,src,count)`, `mica_memeq_full(a,b,count)` and `mica_memzero(dst,count)`. `mica_memeq_full` consumes the requested length without a data-dependent early exit and returns 1 for equal input, 0 otherwise. This **does not certify constant-time execution** on processors with data-dependent memory latency. `mica_memxor` assumes nonoverlapping regions or identical pointers. `mica_memzero` performs explicit byte stores but no C compiler non-elision guarantee exists. x5 and x6 are preserved, x1 carries results. See source comments.

## Small reductions added in the engineering update

`stdlib/reduce.mica` adds `mica_sum8`, `mica_xor8`, and `mica_sum8_f`.
Each takes x1=buffer address and x2=count, returning the reduction in x1.
All bytes are treated as unsigned; the sum wraps at XLEN. No heap or global state.
`mica_sum8_f` requires F and uses post-increment plus `dbnz`.
The empty-buffer case returns zero without dereferencing the pointer.
Only caller-saved registers x1..x4 are modified. Check the address range first.
A runnable example lives in `examples/reduce32.mica`.

## r2 startup and numerical helpers

`runtime/startup/ram_start32.mica` establishes the stack, clears an explicit BSS
range and calls main. The initialized image already contains data at its run
address. The multi-file CRC/UART example builds and runs through the ELF linker.

`stdlib/dsp32.mica` implements signed16-bit dot products using optional M;
results wrap at 32 bits. `examples/fir32.mica` produces16,8,-32,40 and is checked
against independent Python convolution. `stdlib/bounded32.mica` validates two
end-exclusive ranges before calling the F copy routine. Its fifth assembly
argument is x5, preserved by the helper. It is a software prototype, not a new
bounded-stream opcode or an atomic whole-buffer transaction.
