`timescale 1ns / 1ps
module tb_mica_sync_fifo;
  parameter DEPTH = 3;
  reg clk = 0, rst_n = 0, push = 0, pop = 0;
  reg [7 : 0] din = 0;
  wire ready, valid;
  wire [7 : 0] dout;
  wire [$clog2(DEPTH + 1) - 1 : 0] level;
  integer i, j, head = 0, tail = 0, used = 0;
  reg [7 : 0] model[0 : 8191];
  reg [31 : 0] rng = 32'h5eeda123;
  always
    #5 clk = ~clk;
  mica_sync_fifo #(.DEPTH(DEPTH))
      dut(clk,
          rst_n,
          push,
          ready,
          din,
          valid,
          pop,
          dout,
          level);
  task cycle;
    begin
      #1;
      if (level !== used || valid !== (used != 0) ||
          ready !== ((used < DEPTH) || (pop && used != 0)))
        $fatal(1, "FIFO flow control level=%d used=%d", level, used);
      if (valid && dout !== model[head])
        $fatal(1, "FIFO data order");
      if (valid && pop) begin
        head = head + 1;
        used = used - 1;
      end
      if (ready && push) begin
        model[tail] = din;
        tail = tail + 1;
        used = used + 1;
      end
      @(negedge clk);
    end
  endtask
  initial begin
    $dumpfile("mica_sync_fifo.vcd");
    $dumpvars(0, tb_mica_sync_fifo);
    repeat (2) @(negedge clk)
      ;
    rst_n = 1;
    for (j = 0; j < 2; j = j + 1) begin
      // Exercise non-power-of-two wrap, full replacement, blocked push and empty pop.
      for (i = 0; i < 4000; i = i + 1) begin
        rng = rng ^ (rng << 13);
        rng = rng ^ (rng >> 17);
        rng = rng ^ (rng << 5);
        push = rng[0];
        pop = rng[1];
        din = rng[15 : 8];
        cycle;
      end
      rst_n = 0;
      push = 0;
      pop = 0;
      head = 0;
      tail = 0;
      used = 0;
      @(negedge clk);
      if (valid || ready || level != 0)
        $fatal(1, "FIFO reset");
      rst_n = 1;
    end
    $display(
        "mica_sync_fifo PASS: DEPTH=%0d, 8000 deterministic queue operations",
        DEPTH);
    $finish;
  end
endmodule
