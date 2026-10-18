`timescale 1ns / 1ps
module tb_add64;
  logic enable, narrow, sub;
  logic [63 : 0] a, b, full_result, segmented_result, expected;
  logic [63 : 0] random_state = 64'hd4a97f03be618c25;
  mica_add64_full full(enable,
                       narrow,
                       sub,
                       a,
                       b,
                       full_result);
  mica_add64_segmented segmented(enable,
                                 narrow,
                                 sub,
                                 a,
                                 b,
                                 segmented_result);
  task next_random;
    random_state = random_state ^ (random_state << 13);
    random_state = random_state ^ (random_state >> 7);
    random_state = random_state ^ (random_state << 17);
  endtask
  initial begin
    $dumpfile("add64.vcd");
    $dumpvars(0, tb_add64);
    for (integer n = 0; n < 10000; n = n + 1) begin
      next_random();
      a = random_state;
      next_random();
      b = random_state;
      narrow = n % 10 != 0;
      sub = random_state[0];
      enable = n % 17 != 0;
      expected = enable ? (sub ? a - b : a + b) : 64'b0;
      if (narrow)
        expected = {{32{expected[31]}}, expected[31 : 0]};
      #1;
      if (full_result !== expected || segmented_result !== expected)
        $fatal(1, "add64 mismatch");
    end
    $display("add64 PASS 10000 vectors");
    $finish;
  end
endmodule
