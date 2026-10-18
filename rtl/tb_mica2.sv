// MICA-2C fetch, stack-slot memory, and compact counter branch.
// Needs program_mica2.mem32/64 produced by the matching make target.
`timescale 1ns / 1ps
module tb_mica2;
  parameter integer XLEN = 32;
  logic clk = 0, rst_n = 0, tx, halted, fault;
  logic [7 : 0] leds;
  always
    #5 clk = ~clk;
  mica_soc #(.XLEN(XLEN),
             .MICA2(1),
             .TRAP(0),
             .RAM_BYTES(65536),
             .INIT_FILE(XLEN == 64 ? "program_mica2.mem64"
                                   : "program_mica2.mem32"))
      dut(.clk_i(clk),
          .rst_ni(rst_n),
          .irq_i(1'b0),
          .uart_rx_i(1'b1),
          .uart_tx_o(tx),
          .leds_o(leds),
          .halted_o(halted),
          .fault_o(fault));
  initial begin
    repeat (4) @(negedge clk)
      ;
    rst_n = 1;
    repeat (15000) begin
      @(negedge clk);
      if (halted) begin
        if (fault)
          $fatal(1, "MICA-2C fault at PC %h", dut.pc);
        if (dut.a0 !== XLEN'(28))
          $fatal(1, "expected x1=28; got %h", dut.a0);
        $display("MICA-2C PASS XLEN=%0d", XLEN);
        $finish;
      end
    end
    $fatal(1, "MICA-2C simulation timeout");
  end
endmodule
