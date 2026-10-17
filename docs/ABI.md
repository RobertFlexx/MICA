# Calling convention, stack and program image

This is the v1.0 assembly-to-assembly contract. It is not a completed System V, EABI or ISO C ABI.

## Registers

| Register | Purpose | Preservation |
| --- | --- | --- |
| x0 | constant zero | cannot be written |
| x1 to x4 | arguments a0..a3, return value in x1 | caller saved |
| x5 | frame pointer or callee scratch | callee saved |
| x6 | return address (lr) | overwritten by `call` and `jalr` |
| x7 | stack pointer, grows downward | callee must restore |
| x8 to x11 (X) | temporary arguments | caller saved |
| x12 to x15 (X) | saved work registers | callee saved |

`call routine` saves the address after the call instruction in x6. `ret` is a pseudo for `jr x6`. Save x6 around a nested `call`. No implicit shadow stack or interrupt-safe return-link mechanism is currently present.

At a function call boundary, x7 must be 16-byte aligned. The stack is little-endian, grows toward low addresses, and has no red zone. `push` and `pop` currently move x7 by XLEN/8; therefore a single `push` temporarily breaks 16-byte alignment. Do not call another function at that point unless you realign the stack or add another save slot. The MICA64 stack push uses an eight-byte store. Small embedded wrappers are allowed to keep 16-byte stack alignment by allocating a whole 16-byte frame explicitly.

Value results use x1. `mica_udivmod` is a special dual-result helper: quotient in x1, remainder in x2. The library clobber rules appear in `RUNTIME.md`.

## A minimal firmware layout

There is only a flat memory image. The assembler writes bytes in source order. `.text`, `.data`, `.bss`, `.rodata` are readability markers and do not construct independently linked sections. `.org`, `.align` and `.space` write padding directly into that image. Code loads at address zero in the emulator. A real loader must establish the entry address, memory size, stack limit and MMIO map.

On reset the emulator initializes x7 to `(RAM_BYTES - 16) & ~15`. The current RTL initializes x7 to `RAM_BYTES - 16`, which is 16-aligned for the board configurations shown. The physical system still needs stack overflow checks, a memory-protection policy and a trap stack before it can isolate processes.

## Limits that matter when porting C

A C compiler still has to specify aggregate passing, varargs, long double, `setjmp`, structure returns, exception unwinding, TLS, relocation types, stack probes and the instruction used for a system call. None are settled. Calling the header `include/mica.h` is not a promise that the assembly library can currently be linked from arbitrary C.

## Interrupt handler note

MICA-T has no automatic stack frame. `ecall` enters the handler with `epc` set to the next instruction and `eret` resumes at `epc`. `x6` remains the ordinary link register and is not saved by hardware. A handler that modifies application registers must preserve them itself. Nested handlers and privileged task isolation are outside the current profile. See [EXTENSIONS.md](EXTENSIONS.md).
