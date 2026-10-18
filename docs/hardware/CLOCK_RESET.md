# Clock and reset

The Arty wrapper uses the board's 100 MHz clock directly. There is no PLL/MMCM,
clock divider or gated clock in the 2.0 implementation. Clock enables and valid
signals control state updates. The target clock is 100 MHz; Fmax is unmeasured.

Button 0 asserts active-high reset at the board wrapper. A two-flop ASYNC_REG-marked
shift register asynchronously asserts and synchronously releases active-low rst_ni.
Core/UART state has asynchronous assertion; SRAM response-valid flags clear on clk.
Request ready/valid is suppressed during reset. Reset must reach CPU and memory
fabric together. SRAM data bits do not reset. Press reset after configuration during
bring-up.

The external IRQ is a level input synchronized in mica_soc with two marked
flip-flops. Only its level, not narrow pulses, is supported across the clock
boundary. The converted watchdog test shares clk_i and requires no extra CDC. UART
RX has its own two-flop `ASYNC_REG` synchronizer before midpoint sampling. Its FIFO,
CRC engine and MMIO adapter share clk_i; no derived clocks are used. See [peripheral
timing](PERIPHERALS.md).

The board reset declaration has a local Verilator SYNCASYNCNET waiver because this
synchronized release drives both asynchronous core resets and synchronous SRAM
response reset. The waiver does not cover arbitrary CDC logic. There are no ASIC
power-domain or integrated clock-gating cells in this implementation.
