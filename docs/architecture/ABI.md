# MICA assembly ABI

The register table in REGISTERS.md defines preservation. x1..x4 pass arguments; x1
returns a scalar result. The unsigned division helper returns quotient in x1 and
remainder in x2. x5 and SP are callee saved; routines making nested calls save x6. X
uses x8..x11 as caller saved and x12..x15 as callee saved. This is an
assembly ABI. The experimental [C lowering](../toolchain/COMPILER.md) uses its
scalar argument and preservation rules. Aggregate arguments/returns, varargs,
TLS and unwinding remain unspecified.

Stack grows down, is little endian, and is 16-byte aligned at call boundaries. No
red zone. Push/pop expand to an XLEN-byte slot (4 or 8 bytes); callers must restore
16-byte alignment before another call. Return is jr x6. Interrupts have no automatic
frame and must preserve interrupted state separately. The timer scheduler's
x1..x7/EPC frame is an example, not an operating-system ABI.

`runtime/startup/ram_start32.mica` establishes a 64 KiB image's stack, clears the
application's bss_begin..bss_end range, calls main and halts on return. The linked
image already places initialized data at its run address in initialized SRAM.
Separate ROM-to-RAM data-copy startup is not implemented. Link scripts must match
the actual RAM size. The three-file CRC example uses this startup.

`include/mica.h` records prospective C-compatible entry points. The current
libraries use the assembly calling convention; a complete language ABI is still
needed. Source headers document routine-specific
clobbers and special interfaces. ELF image objects currently combine text,
data and materialized BSS in one section; see the
[object-format reference](../toolchain/OBJECT_FORMAT.md).
