// One-byte SPI master, MSB first. Static CPOL/CPHA select modes 0..3.
// Ready/valid request and held response; one CS pulse per byte transaction.
// Standalone peripheral engine for an external bus adapter. Single clk_i domain.
// SPDX-License-Identifier: MIT
module mica_spi_master #(
    parameter CLOCK_DIV = 2, CPOL = 0, CPHA = 0,
    parameter COUNT_W = CLOCK_DIV > 1 ? $clog2(CLOCK_DIV) : 1
) (
    input wire clk_i, rst_ni,
    input wire req_valid_i,
    output wire req_ready_o,
    input wire [7:0] req_data_i,
    output reg rsp_valid_o,
    input wire rsp_ready_i,
    output reg [7:0] rsp_data_o,
    output reg sclk_o, mosi_o,
    input wire miso_i,
    output wire cs_no
);
  localparam integer LAST_TICK = CLOCK_DIV - 1;
  localparam [COUNT_W-1:0] RELOAD = LAST_TICK[COUNT_W-1:0];
  reg busy, trailing, finishing;
  reg [2:0] bit_index;
  reg [7:0] tx_shift, rx_shift;
  reg [COUNT_W-1:0] ticks;
  assign req_ready_o = rst_ni && !busy && !rsp_valid_o;
  assign cs_no = !busy;
  initial begin
    if (CLOCK_DIV < 1 || COUNT_W < 1 || COUNT_W < $clog2(CLOCK_DIV) ||
        (CPOL != 0 && CPOL != 1) || (CPHA != 0 && CPHA != 1))
      $fatal(1, "invalid SPI parameters");
  end
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      busy <= 0; trailing <= 0; finishing <= 0; bit_index <= 7;
      tx_shift <= 0; rx_shift <= 0; ticks <= 0;
      rsp_valid_o <= 0; rsp_data_o <= 0;
      sclk_o <= (CPOL != 0); mosi_o <= 0;
    end else begin
      if (rsp_valid_o && rsp_ready_i) rsp_valid_o <= 0;
      if (req_valid_i && req_ready_o) begin
        busy <= 1; trailing <= 0; finishing <= 0; bit_index <= 7;
        tx_shift <= req_data_i; rx_shift <= 0; ticks <= RELOAD;
        sclk_o <= (CPOL != 0); mosi_o <= CPHA == 0 ? req_data_i[7] : 1'b0;
      end else if (busy) begin
        if (ticks != 0) ticks <= ticks - 1'b1;
        else begin
          ticks <= RELOAD;
          if (finishing) begin
            busy <= 0; finishing <= 0; mosi_o <= 0; rsp_valid_o <= 1;
          end else if (!trailing) begin
            trailing <= 1;
            sclk_o <= (CPOL == 0);
            if (CPHA == 0) rx_shift <= {rx_shift[6:0],miso_i};
            else mosi_o <= tx_shift[7];
          end else begin
            trailing <= 0;
            sclk_o <= (CPOL != 0);
            if (CPHA != 0) rx_shift <= {rx_shift[6:0],miso_i};
            if (bit_index == 0) begin
              // Hold CS for a half period after the final sampling edge.
              finishing <= 1;
              rsp_data_o <= CPHA == 0 ? rx_shift : {rx_shift[6:0],miso_i};
            end else begin
              bit_index <= bit_index - 1'b1;
              tx_shift <= {tx_shift[6:0],1'b0};
              if (CPHA == 0) mosi_o <= tx_shift[6];
            end
          end
        end
      end
    end
  end
endmodule
