# Emulator CLI debugger

Start with `mica-run --debug firmware.bin`. Commands read from stdin and report
state on stderr, so scripted sessions are possible. Addresses/numbers accept
C-style0x prefixes.

| Command | Effect |
| --- | --- |
| regs / r | PC, retirement/step counts and all scalar registers |
| step [N] / s | execute up to N instructions, default1 |
| continue / c | run until halt, breakpoint, watchpoint or one-million-step guard |
| break ADDR / delete ADDR | add/remove an instruction boundary stop |
| watch ADDR COUNT / unwatch | stop after overlapping RAM reads/writes; clear all watches |
| mem ADDR COUNT | inspect up to 4096 RAM bytes |
| csr ID | read a defined CSR using normal rights |
| setreg N VALUE | modify a scalar register; x0 remains zero |
| setpc ADDR | set an even mapped PC and release halt |
| quit / q | leave debugger |

Breakpoint continue steps over the current stopped instruction before checking
the next boundary. Watchpoints stop after the complete instruction; they do not
roll back memory. Debug access is an explicit host capability, not a hardware
privilege bypass instruction. There is no GDB RSP stub, symbol-aware source
stepping, FPGA debug module or external halt input in r2.
