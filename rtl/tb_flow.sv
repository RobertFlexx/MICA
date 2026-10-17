// RTL smoke test for FLOW=1 in XLEN32 or XLEN64. Requires a matching ROM.
// This is a test source, not evidence that the HDL has passed a simulator.
`timescale 1ns / 1ps
module tb_flow;
  parameter integer XLEN = 32;
  logic clk = 0, rst_n = 0, uart_tx, halted, fault;
  logic [7 : 0] leds;
  always
    #5 clk = ~clk;
  mica_soc #(.XLEN(XLEN),
             .FLOW(1),
             .RAM_BYTES(65536),
             .INIT_FILE("program_flow.mem8"))
      dut(.clk_i(clk),
          .rst_ni(rst_n),
          .irq_i(1'b0),
          .uart_tx_o(uart_tx),
          .leds_o(leds),
          .halted_o(halted),
          .fault_o(fault));
  initial begin
    repeat (4) @(negedge clk)
      ;
    rst_n = 1;
    repeat (10000) begin
      @(negedge clk);
      if (halted) begin
        if (fault)
          $fatal(1, "FLOW core fault at pc=%h", dut.pc);
        if (XLEN == 32) begin
          if (dut.a0 !== 32'd3)
            $fatal(1, "FLOW32 expected x1=3, got=%h", dut.a0);
        end else begin
          if (dut.a0 !== XLEN'(64'h0000000200000001))
            $fatal(1, "FLOW64 x1 mismatch");
        end
        $display("MICA FLOW RTL smoke PASS XLEN=%0d", XLEN);
        $finish;
      end
    end
    $fatal(1, "FLOW RTL simulation timeout");
  end
endmodule
