# Transactional reference microarchitecture

`mica_core_txn` is a single-issue, nonoverlapped multicycle implementation of
the scalar architecture. Parameters select XLEN32/64, XREG, M, F, B, T, PERF,
RAM_BYTES and FETCH_REUSE. The register array has8 or16 entries. Disabled
multiply/bit/CSR paths are explicitly isolated so synthesis can remove them.

| State | Work |
| --- | --- |
| START | inspect interrupts; initialize the next instruction fetch |
| LOOKUP | compare aligned-word reuse tag |
| IREQ/IWAIT | hold request, then await owned instruction response |
| PARCEL | select first or second halfword; obtain another word when needed |
| DECODE | validate all fields, read operands, compute pending effects |
| DREQ/DWAIT | hold data request, wait for successful completion or fault |
| COMMIT | apply pending register/CSR writes, update PC, issue retirement event |
| STOP | halt until reset |

Decode produces pending writes; it does not write registers. F can queue two
distinct writes. A fault discards both. Interrupt entry occurs only at START,
after prior completion. A data error uses the held instruction PC/address.

The one-word fetch reuse buffer keeps an aligned tag and 32-bit word. It can
supply adjacent short instructions and either parcel of a long instruction.
Stores, redirects, trap entry and fence.i invalidate it. With reuse disabled,
the same architectural trace is produced with more memory transactions.
It is not an instruction cache or loop buffer. There are no forwarded operand
paths, speculative memory operations, caches or multicore arbitration.

`mica_soc` connects the core to synchronous Verilog SRAM, UART TX and GPIO.
Its external IRQ synchronizer precedes core irq_i. UART writes wait for the
transmitter to become idle; polling firmware remains valid. Optional UART RX/FIFO and a VHDL CRC engine use the same transactional bus; see [peripherals](PERIPHERALS.md).
The VHDL watchdog is separately verified and can feed the external IRQ through
the documented GHDL converted-netlist integration test.
