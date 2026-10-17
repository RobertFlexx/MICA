// 8N1 UART transmit peripheral, 3.3V FPGA TX output, SPDX-License-Identifier: MIT.
module mica_uart_tx
    #(parameter integer CLOCK_HZ = 12000000, BAUD = 115200)
    (input logic clk_i,
     input logic rst_ni,
     input logic send_i,
     input logic [7 : 0] data_i,
     output logic busy_o,
     output logic uart_tx_o);
  localparam integer DIV = (CLOCK_HZ + BAUD / 2) / BAUD;
  localparam integer CW = (DIV > 1) ? $clog2(DIV) : 1;
  logic [CW - 1 : 0] count;
  logic [3 : 0] bit_index;
  logic [9 : 0] frame;
  always_ff @(posedge clk_i or negedge rst_ni) begin
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
        count <= CW'(DIV - 1);
        bit_index <= 0;
        uart_tx_o <= 0;
      end
    end else if (count != 0)
      count <= count - 1'b1;
    else begin
      count <= CW'(DIV - 1);
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
