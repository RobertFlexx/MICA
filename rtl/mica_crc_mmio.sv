// Transactional MMIO adapter for mica_crc32 (VHDL or its GHDL netlist).
// Request acceptance owns one held response. No side effect before acceptance.
// SPDX-License-Identifier: MIT
module mica_crc_mmio (
  input logic clk_i,rst_ni,
  input logic req_valid, output logic req_ready,
  input logic [3:0] req_addr, input logic req_write,
  input logic [2:0] req_size, input logic [31:0] req_wdata,
  output logic rsp_valid, input logic rsp_ready,
  output logic [31:0] rsp_rdata, output logic rsp_error,
  output logic clear_o,byte_valid_o, output logic [7:0] byte_o,
  input logic byte_ready_i,busy_i,
  input logic [31:0] crc_i,count_i
);
  logic legal,wait_engine;
  wire unused_wdata=^req_wdata[31:8];
  assign legal = req_size<=2 && (req_addr==0 || (req_addr==4 && req_write)
                           || ((req_addr==8 || req_addr==12) && !req_write));
  assign wait_engine = legal && ((req_addr==4 && !byte_ready_i)
                           || (req_addr==8 && busy_i));
  assign req_ready = rst_ni && (!rsp_valid || rsp_ready) && !wait_engine;
  // CTRL does not wait for the engine. Keep clear independent of ready to
  // avoid a combinational cycle through the engine's clear-gated byte_ready.
  assign clear_o = rst_ni && req_valid && (!rsp_valid || rsp_ready) && legal && req_write && req_addr==0 && req_wdata[0];
  assign byte_valid_o = req_valid && req_ready && legal && req_write && req_addr==4;
  assign byte_o = req_wdata[7:0];
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if(!rst_ni) begin rsp_valid<=0;rsp_rdata<=0;rsp_error<=0;end
    else begin
      if(rsp_ready) rsp_valid<=0;
      if(req_valid && req_ready) begin
        rsp_valid<=1;rsp_error<=!legal;rsp_rdata<=0;
        if(legal && !req_write) case(req_addr)
          0: rsp_rdata<={31'b0,busy_i};
          8: rsp_rdata<=crc_i;
          12: rsp_rdata<=count_i;
          default: begin end
        endcase
      end
    end
  end
endmodule
