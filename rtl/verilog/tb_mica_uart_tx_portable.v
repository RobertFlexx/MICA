`timescale 1ns / 1ps
module tb_mica_uart_tx_portable;
  reg clk_i = 0, rst_ni = 0, send_i = 0;
  reg [7 : 0] data_i = 0;
  wire busy_o, uart_tx_o;
  integer value, bit_number, tick;
  reg [9 : 0] expected;
  always
    #5 clk_i = ~clk_i;
  mica_uart_tx_portable #(.CLOCK_HZ(50),
                          .BAUD(10))
      dut(.clk_i(clk_i),
          .rst_ni(rst_ni),
          .send_i(send_i),
          .data_i(data_i),
          .busy_o(busy_o),
          .uart_tx_o(uart_tx_o));
  initial begin
    repeat (2) @(negedge clk_i)
      ;
    rst_ni = 1;
    for (value = 0; value < 256; value = value + 1) begin
      data_i = value[7 : 0];
      send_i = 1;
      @(negedge clk_i);
      send_i = 0;
      expected = {1'b1, value[7 : 0], 1'b0};
      for (bit_number = 0; bit_number < 10; bit_number = bit_number + 1)
        for (tick = 0; tick < 5; tick = tick + 1) begin
          if (!busy_o || uart_tx_o !== expected[bit_number])
            $fatal(1, "TX byte=%0d bit=%0d tick=%0d", value, bit_number, tick);
          // A busy transmitter must ignore this competing request.
          send_i = (bit_number == 3);
          data_i = ~value[7 : 0];
          @(negedge clk_i);
        end
      send_i = 0;
      if (busy_o || !uart_tx_o)
        $fatal(1, "TX completion");
    end
    send_i = 1;
    @(negedge clk_i);
    send_i = 0;
    repeat (7) @(negedge clk_i)
      ;
    rst_ni = 0;
    #1;
    if (busy_o || !uart_tx_o)
      $fatal(1, "TX asynchronous reset");
    $display("UART TX PASS: all 256 bytes, busy requests, reset");
    $finish;
  end
  initial begin
    #2000000;
    $fatal(1, "TX timeout");
  end
endmodule
