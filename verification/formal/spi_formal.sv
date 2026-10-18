// Ready/valid ownership, held responses, idle clock and bounded completion.
// Serial data correctness is checked independently by the four-mode slave TB.
module spi_contract #(parameter CPOL = 0, CPHA = 0)
    (input clk_i, rst_ni, valid_i, ready_i, miso_i,
     input [7:0] data_i);
  wire req_ready_o, rsp_valid_o, sclk_o, mosi_o, cs_no;
  wire [7:0] rsp_data_o;
  mica_spi_master #(.CLOCK_DIV(1), .CPOL(CPOL), .CPHA(CPHA)) dut(
      .clk_i(clk_i), .rst_ni(rst_ni), .req_valid_i(valid_i), .req_ready_o(req_ready_o),
      .req_data_i(data_i), .rsp_valid_o(rsp_valid_o), .rsp_ready_i(ready_i),
      .rsp_data_o(rsp_data_o), .miso_i(miso_i), .sclk_o(sclk_o), .mosi_o(mosi_o), .cs_no(cs_no));
  reg past_valid = 0, pending = 0;
  reg [5:0] age = 0;
  always @(posedge clk_i) begin
    past_valid <= 1;
    if (!past_valid) assume(!rst_ni);
    if (!rst_ni) begin
      pending <= 0;
      age <= 0;
    end else begin
      assert(age < 20);
      assert(!rsp_valid_o || pending);
      assert(!req_ready_o || !pending);
      if (cs_no) assert(sclk_o == CPOL);
      if (valid_i && req_ready_o) begin
        assert(!pending);
        pending <= 1;
        age <= 0;
      end else if (rsp_valid_o && ready_i) begin
        pending <= 0;
        age <= 0;
      end else if (pending && !rsp_valid_o) age <= age + 1;
      if (past_valid && $past(rst_ni && rsp_valid_o && !ready_i)) begin
        assert(rsp_valid_o);
        assert($stable(rsp_data_o));
        assert(cs_no);
      end
    end
  end
endmodule

module spi_formal(input clk_i, rst_ni, valid_i, ready_i, miso_i, input [7:0] data_i);
  genvar mode;
  generate for(mode=0; mode<4; mode=mode+1) begin: modes
    spi_contract #(.CPOL(mode/2), .CPHA(mode%2)) contract(.*);
  end endgenerate
endmodule
