`timescale 1ns / 1ps
module tb_mica_sram;
  reg clk = 0;
  always
    #5 clk = ~clk;
  reg rst_n = 0, req_valid = 0, req_write = 0;
  reg [3 : 0] req_word_addr = 0;
  reg [31 : 0] req_wdata = 0;
  reg [3 : 0] req_wstrb = 0;
  wire rsp_valid;
  wire [31 : 0] rsp_rdata;
  mica_sram #(.DATA_W(32),
              .ADDR_W(4))
      dut(.clk(clk),
          .rst_n(rst_n),
          .req_valid(req_valid),
          .req_write(req_write),
          .req_word_addr(req_word_addr),
          .req_wdata(req_wdata),
          .req_wstrb(req_wstrb),
          .rsp_valid(rsp_valid),
          .rsp_rdata(rsp_rdata));
  initial begin
    @(negedge clk);
    rst_n = 1;
    req_valid = 1;
    req_write = 1;
    req_word_addr = 3;
    req_wdata = 32'h11223344;
    req_wstrb = 4'hf;
    @(posedge clk);
    #1;
    if (!rsp_valid)
      $fatal(1, "missing write response");
    @(negedge clk);
    req_write = 0;
    @(posedge clk);
    #1;
    if (!rsp_valid || rsp_rdata !== 32'h11223344)
      $fatal(1, "full write failed");
    @(negedge clk);
    req_write = 1;
    req_wstrb = 4'b0010;
    req_wdata = 32'hffffaaff;
    @(negedge clk);
    req_write = 0;
    @(posedge clk);
    #1;
    if (rsp_rdata !== 32'h1122aa44)
      $fatal(1, "byte write failed");
    @(negedge clk);
    req_valid = 0;
    @(posedge clk);
    #1;
    if (rsp_valid)
      $fatal(1, "unexpected response");
    $display("mica_sram PASS");
    $finish;
  end
endmodule
