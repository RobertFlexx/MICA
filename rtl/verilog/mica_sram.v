// Portable, synchronous, single-port SRAM with byte writes.
// Old data is returned when a read and write hit the same word.
// There is no bus arbiter here. One request in, one response out next clock.
// SPDX-License-Identifier: MIT
module mica_sram #(
  parameter DATA_W = 32,
  parameter ADDR_W = 10
) (
  input wire clk,
  input wire rst_n,
  input wire req_valid,
  input wire req_write,
  input wire [ADDR_W-1:0] req_word_addr,
  input wire [DATA_W-1:0] req_wdata,
  input wire [DATA_W/8-1:0] req_wstrb,
  output reg rsp_valid,
  output reg [DATA_W-1:0] rsp_rdata
);
  localparam WORDS = (1 << ADDR_W);
  reg [DATA_W-1:0] mem [0:WORDS-1];
  integer lane;
  always @(posedge clk) begin
    if (!rst_n) begin
      rsp_valid <= 1'b0;
      rsp_rdata <= {DATA_W{1'b0}};
    end else begin
      rsp_valid <= req_valid;
      if (req_valid) begin
        rsp_rdata <= mem[req_word_addr];
        if (req_write)
          for (lane = 0; lane < DATA_W/8; lane = lane + 1)
            if (req_wstrb[lane])
              mem[req_word_addr][8*lane +: 8] <= req_wdata[8*lane +: 8];
      end
    end
  end
endmodule
