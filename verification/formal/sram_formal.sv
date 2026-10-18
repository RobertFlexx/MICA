module sram_formal (
  input clk_i,rst_ni,i_req_valid,i_rsp_ready,d_req_valid,d_rsp_ready,d_req_write,
  input [31:0] i_req_addr,d_req_addr,d_req_wdata,
  input [2:0] d_req_size,input [3:0] d_req_wstrb
);
  wire i_req_ready,i_rsp_valid,i_rsp_error,d_req_ready,d_rsp_valid,d_rsp_error;
  wire [31:0] i_rsp_rdata,d_rsp_rdata;
  mica_sram_txn #(.RAM_BYTES(64),.INIT_FILE("")) dut (.*);
  reg past_valid=0;
  reg i_pending=0,d_pending=0;
  always @(posedge clk_i) begin
    past_valid<=1;
    if(!past_valid) assume(!rst_ni);
    if(!rst_ni) begin i_pending<=0;d_pending<=0;end
    else begin
      if(i_rsp_valid && i_rsp_ready) i_pending<=0;
      if(i_req_valid && i_req_ready) i_pending<=1;
      if(d_rsp_valid && d_rsp_ready) d_pending<=0;
      if(d_req_valid && d_req_ready) d_pending<=1;
      assert(!i_rsp_valid || i_pending);
      assert(!d_rsp_valid || d_pending);
    end
    if(past_valid && rst_ni && $past(rst_ni)) begin
      if($past(i_rsp_valid && !i_rsp_ready)) begin
        assert(i_rsp_valid);assert($stable(i_rsp_rdata));assert($stable(i_rsp_error));
      end
      if($past(d_rsp_valid && !d_rsp_ready)) begin
        assert(d_rsp_valid);assert($stable(d_rsp_rdata));assert($stable(d_rsp_error));
      end
    end
    if(past_valid && !$past(rst_ni)) begin assert(!i_rsp_valid);assert(!d_rsp_valid);end
  end
endmodule
