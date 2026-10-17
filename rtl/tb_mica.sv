// Functional ROM-level smoke test. Must load examples/arithmetic32.mica
// for XLEN32, or examples/arithmetic64.mica for XLEN64.
// This is NOT a comprehensive verification environment.
`timescale 1ns / 1ps
module tb_mica;
  parameter integer XLEN = 32;
  localparam logic [XLEN - 1 : 0] EXPECT_A0 = (XLEN == 32)
                                                  ? XLEN'(42)
                                                  : XLEN'(64'h0123456889abcdee);
  logic clk = 0, rst_n = 0, uart_tx, halted, fault;
  logic [7 : 0] leds;
  always
    #5 clk = ~clk;
  mica_soc #(.XLEN(XLEN),
             .RAM_BYTES(65536),
             .INIT_FILE("program.mem8"))
      dut(.clk_i(clk),
          .rst_ni(rst_n),
          .uart_tx_o(uart_tx),
          .leds_o(leds),
          .halted_o(halted),
          .fault_o(fault));
  initial begin
    repeat (5) @(negedge clk)
      ;
    rst_n = 1;
    repeat (100000) begin
      @(negedge clk);
      if (halted) begin
        if (fault)
          $fatal(1, "MICA RTL illegal instruction or alignment fault; PC=%h",
                 dut.pc);
        if (dut.a0 !== EXPECT_A0)
          $fatal(1, "MICA RTL expected a0=%h, got=%h", EXPECT_A0, dut.a0);
        $display("MICA RTL smoke-test PASS: XLEN=%0d, a0=%h, LEDs=%h", XLEN,
                 dut.a0, leds);
        $finish;
      end
    end
    $fatal(1, "MICA RTL simulation timeout");
  end
endmodule
