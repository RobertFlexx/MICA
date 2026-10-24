// MICA on Digilent Arty A7. Demo top for a block-RAM firmware image.
// Confirm timing, resource utilization and pin constraints before using hardware.
// No external wiring is required beyond the board's onboard USB/JTAG/UART.
// SPDX-License-Identifier: MIT
module mica_arty_a7
    #(parameter integer XLEN = 32,
      parameter integer FLOW = 1,
      parameter integer BITOPS = 0,
      parameter integer TRAP = 1,
      parameter integer PERF = 1,
      parameter integer MICA2 = 0,
      parameter integer RAM_BYTES = 4096,
      parameter integer UART_RX = 1,
      parameter integer CRC_ENABLE = 0,
      parameter integer WATCHDOG_ENABLE = 0, REG_PARITY = 0,
      parameter INIT_FILE = "program.mem32")
    (input logic CLK100MHZ,
     input logic btn_reset,
     output logic [3 : 0] led,
     input logic uart_rxd,
     output logic uart_txd);
  // The core asserts reset asynchronously; SRAM response flags clear on clk.
  // Both remain reset until this two-flop release synchronizer finishes.
  /* verilator lint_off SYNCASYNCNET */
  (* ASYNC_REG = "TRUE" *) logic [1 : 0] rst_release;
  /* verilator lint_on SYNCASYNCNET */
  logic rst_ni;
  logic [7 : 0] unused_gpio;
  logic halted, fault;
  always_ff @(posedge CLK100MHZ or posedge btn_reset) begin
    if (btn_reset)
      rst_release <= 2'b00;
    else
      rst_release <= {rst_release[0], 1'b1};
  end
  assign rst_ni = rst_release[1];
  mica_soc #(.XLEN(XLEN),
             .FLOW(FLOW),
             .BITOPS(BITOPS),
             .TRAP(TRAP),
             .PERF(PERF),
             .MICA2(MICA2),
             .RAM_BYTES(RAM_BYTES),
             .UART_RX(UART_RX),
             .CRC_ENABLE(CRC_ENABLE),
             .WATCHDOG_ENABLE(WATCHDOG_ENABLE),
             .REG_PARITY(REG_PARITY),
             .CLOCK_HZ(100000000),
             .BAUD(115200),
             .INIT_FILE(INIT_FILE))
      soc(.clk_i(CLK100MHZ),
          .rst_ni(rst_ni),
          .irq_i(1'b0),
          .uart_rx_i(uart_rxd),
          .uart_tx_o(uart_txd),
          .leds_o(unused_gpio),
          .halted_o(halted),
          .fault_o(fault));
  assign led = {fault, halted, unused_gpio[1 : 0]};
endmodule
