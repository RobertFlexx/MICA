// 8N1 UART transmit peripheral, 3.3V FPGA TX output, SPDX-License-Identifier: MIT.
module mica_uart_tx
    #(parameter integer CLOCK_HZ = 12000000, BAUD = 115200)
    (input logic clk_i,
     input logic rst_ni,
     input logic send_i,
     input logic [7 : 0] data_i,
     output logic busy_o,
     output logic uart_tx_o);
  mica_uart_tx_portable #(.CLOCK_HZ(CLOCK_HZ), .BAUD(BAUD)) implementation (
      .clk_i(clk_i), .rst_ni(rst_ni), .send_i(send_i), .data_i(data_i),
      .busy_o(busy_o), .uart_tx_o(uart_tx_o));
endmodule
