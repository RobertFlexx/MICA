# Memory ordering and atomics

The supported hardware configuration is one uncached hart with shared code/data
SRAM and ordered MMIO. Instruction and data ports are separate transactions;
the multicycle CPU never overlaps their accepted operations. A completed
instruction precedes the next instruction's memory effect. Fused F updates
commit with their memory completion. Fences complete the same sequential order.
Self-modifying code is supported with store invalidation plus fence.i before
executing changed bytes.

MICA-A currently exists in the single-hart emulator only. Aligned .w/.q LR,
SC, exchange and addition access mapped RAM, never MMIO. LR reserves the exact
address and width. Any overlapping store invalidates it, SC always clears it,
and trap entry clears it. SC succeeds only when both address and width match;
its return is 0 on success and 1 on failure. Failed SC still checks the mapped,
aligned address, but performs no store. Old .w values zero extend to XLEN.
AMOs read old memory, calculate the low-width replacement, write, then return
old memory as one instruction. These are sequential interpreter operations.

For a future MICA-MP implementation the intended research baseline is sequential
consistency across ordinary memory and atomics, with a single global ordering
point and fences ordering MMIO as well. This is a proposal: no shared arbiter,
coherence protocol, inter-core interrupt delivery or multi-hart happens-before
implementation is supplied. Firmware using the current A library does not
establish multicore hardware support. No progress/fairness guarantee for LR/SC
across harts or coherent DMA is claimed.
