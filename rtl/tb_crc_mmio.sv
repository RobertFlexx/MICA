`timescale 1ns / 1ps
module tb_crc_mmio;
  logic clk = 0, rst_n = 0, valid = 0, ready, write = 0, rv, rr = 0, error;
  logic [3 : 0] addr = 0;
  logic [2 : 0] size = 2;
  logic [31 : 0] wd = 0, rd, crc, count, result;
  logic clear, push, br, busy;
  logic [7 : 0] byte_data;
  integer i;
  always
    #5 clk = ~clk;
  mica_crc_mmio bridge(clk,
                       rst_n,
                       valid,
                       ready,
                       addr,
                       write,
                       size,
                       wd,
                       rv,
                       rr,
                       rd,
                       error,
                       clear,
                       push,
                       byte_data,
                       br,
                       busy,
                       crc,
                       count);
  mica_crc32 engine(clk,
                    rst_n,
                    clear,
                    push,
                    br,
                    byte_data,
                    busy,
                    crc,
                    count);
  task transaction
      (input [3 : 0] a,
       input wr,
       input [31 : 0] value,
       input [2 : 0] width,
       input bad);
    logic [31 : 0] held;
    begin
      @(negedge clk);
      addr = a;
      write = wr;
      wd = value;
      size = width;
      valid = 1;
      do
        @(posedge clk);
      while (!ready);
      @(negedge clk);
      valid = 0;
      held = rd;
      repeat (3) begin
        if (!rv || error !== bad || rd !== held || ready)
          $fatal(1, "CRC response backpressure");
        @(negedge clk);
      end
      result = held;
      rr = 1;
      @(negedge clk);
      rr = 0;
      if (rv)
        $fatal(1, "CRC response consumed twice");
    end
  endtask
  initial begin
    $dumpfile("crc-mmio.vcd");
    $dumpvars(0, tb_crc_mmio);
    repeat (3) @(negedge clk)
      ;
    rst_n = 1;
    transaction(8, 0, 0, 2, 0);
    if (result != 0)
      $fatal(1, "empty CRC");
    for (i = 1; i <= 9; i = i + 1)
      transaction(4, 1, 32'(48 + i), 0, 0);
    transaction(8, 0, 0, 2, 0);
    if (result !== 32'hcbf43926)
      $fatal(1, "CRC result %x", result);
    transaction(12, 0, 0, 2, 0);
    if (result != 9)
      $fatal(1, "CRC count");
    transaction(4, 0, 0, 2, 1);
    transaction(8, 1, 0, 2, 1);
    transaction(0, 1, 1, 3, 1);
    transaction(12, 0, 0, 2, 0);
    if (result != 9)
      $fatal(1, "illegal CRC access side effect");
    transaction(0, 1, 1, 2, 0);
    transaction(8, 0, 0, 2, 0);
    if (result != 0)
      $fatal(1, "CRC clear");
    @(negedge clk);
    addr = 4;
    wd = 42;
    write = 1;
    valid = 1;
    do
      @(posedge clk);
    while (!ready);
    @(negedge clk);
    valid = 0;
    rst_n = 0;
    @(negedge clk);
    if (rv || count != 0 || busy || crc != 0)
      $fatal(1, "CRC reset outstanding");
    rst_n = 1;
    transaction(12, 0, 0, 2, 0);
    if (result != 0)
      $fatal(1, "CRC reset count");
    $display(
        "CRC MMIO PASS: GHDL VHDL engine, held responses, stalls, faults, reset");
    $finish;
  end
  initial begin
    #100000;
    $fatal(1, "CRC MMIO timeout");
  end
endmodule
