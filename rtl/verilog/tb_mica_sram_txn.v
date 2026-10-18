`timescale 1ns / 1ps
module tb_mica_sram_txn;
  reg clk_i = 0, rst_ni = 0;
  always
    #5 clk_i = ~clk_i;
  reg i_req_valid = 0, i_rsp_ready = 0, d_req_valid = 0, d_rsp_ready = 0,
      d_req_write = 0;
  reg [31 : 0] i_req_addr = 0, d_req_addr = 0, d_req_wdata = 0;
  reg [2 : 0] d_req_size = 2;
  reg [3 : 0] d_req_wstrb = 15;
  wire i_req_ready, i_rsp_valid, i_rsp_error, d_req_ready, d_rsp_valid,
       d_rsp_error;
  wire [31 : 0] i_rsp_rdata, d_rsp_rdata;
  mica_sram_txn #(.RAM_BYTES(64),
                  .INIT_FILE(""))
      dut(.clk_i(clk_i),
          .rst_ni(rst_ni),
          .i_req_valid(i_req_valid),
          .i_req_ready(i_req_ready),
          .i_req_addr(i_req_addr),
          .i_rsp_valid(i_rsp_valid),
          .i_rsp_ready(i_rsp_ready),
          .i_rsp_rdata(i_rsp_rdata),
          .i_rsp_error(i_rsp_error),
          .d_req_valid(d_req_valid),
          .d_req_ready(d_req_ready),
          .d_req_addr(d_req_addr),
          .d_req_write(d_req_write),
          .d_req_size(d_req_size),
          .d_req_wdata(d_req_wdata),
          .d_req_wstrb(d_req_wstrb),
          .d_rsp_valid(d_rsp_valid),
          .d_rsp_ready(d_rsp_ready),
          .d_rsp_rdata(d_rsp_rdata),
          .d_rsp_error(d_rsp_error));
  initial begin
    $dumpfile("sram_txn.vcd");
    $dumpvars(0, tb_mica_sram_txn);
    @(negedge clk_i);
    rst_ni = 1;
    d_req_valid = 1;
    d_req_write = 1;
    d_req_addr = 4;
    d_req_wdata = 32'h11223344;
    @(negedge clk_i);
    d_req_valid = 0;
    if (!d_rsp_valid || d_req_ready)
      $fatal(1, "missing response/backpressure");
    repeat (5) begin
      @(negedge clk_i);
      if (!d_rsp_valid || d_rsp_error || d_req_ready)
        $fatal(1, "response not held");
    end
    d_rsp_ready = 1;
    @(negedge clk_i);
    d_rsp_ready = 0;
    i_req_valid = 1;
    i_req_addr = 4;
    @(negedge clk_i);
    i_req_valid = 0;
    if (!i_rsp_valid || i_rsp_rdata !== 32'h11223344 || i_rsp_error)
      $fatal(1, "instruction read");
    repeat (3) @(negedge clk_i)
      ;
    if (!i_rsp_valid || i_rsp_rdata !== 32'h11223344)
      $fatal(1, "fetch response not held");
    i_rsp_ready = 1;
    d_req_valid = 1;
    d_req_write = 1;
    d_req_addr = 5;
    d_req_size = 0;
    d_req_wstrb = 2;
    d_req_wdata = 32'h0000aa00;
    @(negedge clk_i);
    d_req_valid = 0;
    d_rsp_ready = 1;
    @(negedge clk_i);
    d_req_valid = 1;
    d_req_write = 0;
    d_req_addr = 4;
    d_req_size = 2;
    @(negedge clk_i);
    d_req_valid = 0;
    if (d_rsp_rdata !== 32'h1122aa44)
      $fatal(1, "byte write");
    d_req_valid = 1;
    d_req_write = 1;
    d_req_addr = 64;
    @(negedge clk_i);
    d_req_valid = 0;
    d_rsp_ready = 0;
    if (!d_rsp_valid || !d_rsp_error)
      $fatal(1, "unmapped request did not fault");
    rst_ni = 0;
    @(negedge clk_i);
    if (d_rsp_valid || i_rsp_valid)
      $fatal(1, "reset failed to cancel responses");
    $display("mica_sram_txn PASS");
    $finish;
  end
endmodule
