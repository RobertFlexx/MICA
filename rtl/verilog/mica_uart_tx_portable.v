// Portable Verilog-2005 UART transmitter. 8 data bits, no parity, one stop bit.
// send_i is accepted only while idle. Reset abandons a partial frame.
// SPDX-License-Identifier: MIT
module mica_uart_tx_portable
    #(parameter CLOCK_HZ = 12000000, BAUD = 115200,
      parameter DIVISOR = (BAUD > 0 ? (CLOCK_HZ + BAUD / 2) / BAUD : 1),
      parameter COUNT_W = (DIVISOR > 1 ? $clog2(DIVISOR) : 1))
    (input wire clk_i, rst_ni, send_i,
     input wire [7 : 0] data_i,
     output reg busy_o, uart_tx_o);
  localparam integer LAST_TICK = DIVISOR - 1;
  localparam [COUNT_W - 1 : 0] RELOAD = LAST_TICK[COUNT_W - 1 : 0];
  reg [COUNT_W - 1 : 0] count;
  reg [3 : 0] bit_index;
  reg [9 : 0] frame;
  initial begin
    if (CLOCK_HZ <= 0 || BAUD <= 0 || DIVISOR < 1 || COUNT_W < 1 ||
        COUNT_W < $clog2(DIVISOR))
      $fatal(1, "invalid UART TX parameters");
  end
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      busy_o <= 0;
      uart_tx_o <= 1;
      count <= 0;
      bit_index <= 0;
      frame <= 10'h3ff;
    end else if (!busy_o) begin
      uart_tx_o <= 1;
      if (send_i) begin
        frame <= {1'b1, data_i, 1'b0};
        busy_o <= 1;
        count <= RELOAD;
        bit_index <= 0;
        uart_tx_o <= 0;
      end
    end else if (count != 0)
      count <= count - 1'b1;
    else begin
      count <= RELOAD;
      if (bit_index == 9) begin
        busy_o <= 0;
        uart_tx_o <= 1;
      end else begin
        bit_index <= bit_index + 1'b1;
        uart_tx_o <= frame[bit_index + 1'b1];
      end
    end
  end
endmodule
