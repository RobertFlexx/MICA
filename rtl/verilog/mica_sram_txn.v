// Dual-port synchronous SRAM; one held response per port. MIT.
// Same-word cross-port read/write is unspecified; core phases never overlap.
module mica_sram_txn #(
  parameter DATA_W=32, ADDR_W=32, RAM_BYTES=65536, INIT_FILE=""
) (
  input wire clk_i, rst_ni,
  input wire i_req_valid, output wire i_req_ready,
  input wire [ADDR_W-1:0] i_req_addr,
  output reg i_rsp_valid, input wire i_rsp_ready,
  output wire [31:0] i_rsp_rdata, output reg i_rsp_error,
  input wire d_req_valid, output wire d_req_ready,
  input wire [ADDR_W-1:0] d_req_addr,
  input wire d_req_write, input wire [2:0] d_req_size,
  input wire [DATA_W-1:0] d_req_wdata,
  input wire [DATA_W/8-1:0] d_req_wstrb,
  output reg d_rsp_valid, input wire d_rsp_ready,
  output reg [DATA_W-1:0] d_rsp_rdata, output reg d_rsp_error
);
  localparam BYTES=DATA_W/8, WORDS=RAM_BYTES/BYTES, SHIFT=$clog2(BYTES);
  (* ram_style="block" *) reg [DATA_W-1:0] mem[0:WORDS-1];
  integer j;
  reg [DATA_W-1:0] i_word;
  localparam INDEX_W=$clog2(WORDS);
  localparam [2:0] SIZE_LIMIT=SHIFT[2:0];
  // INIT_FILE contains DATA_W-bit little-endian words, not individual bytes.
  initial begin
    if(INIT_FILE!="") $readmemh(INIT_FILE,mem);
  end
  assign i_req_ready=rst_ni && (!i_rsp_valid || i_rsp_ready);
  assign d_req_ready=rst_ni && (!d_rsp_valid || d_rsp_ready);
  wire i_bad=((i_req_addr>>32)!=0 || i_req_addr[31:0]>RAM_BYTES-4) || (i_req_addr[1:0]!=0);
  wire d_bad=(d_req_size>SIZE_LIMIT) || ((d_req_addr>>32)!=0) || (d_req_addr[31:0]>RAM_BYTES-(32'd1<<d_req_size)) ||
    ((d_req_addr[31:0] & ((32'd1<<d_req_size)-1))!=0);
  generate if(DATA_W==64) begin: fetch64
    reg select_upper;
    always @(posedge clk_i)
      if(i_req_valid && i_req_ready && !i_bad) select_upper<=i_req_addr[2];
    assign i_rsp_rdata=select_upper ? i_word[63:32]:i_word[31:0];
  end else begin: fetch32
    assign i_rsp_rdata=i_word;
  end endgenerate
  // Read data has no reset, permitting block RAM inference.
  always @(posedge clk_i) begin
    if(i_req_valid && i_req_ready && !i_bad) begin
      i_word<=mem[i_req_addr[SHIFT+:INDEX_W]];
    end
    if(d_req_valid && d_req_ready && !d_bad) begin
      d_rsp_rdata<=mem[d_req_addr[SHIFT+:INDEX_W]];
      if(d_req_write)
        for(j=0;j<BYTES;j=j+1)
          if(d_req_wstrb[j]) mem[d_req_addr[SHIFT+:INDEX_W]][8*j+:8]<=d_req_wdata[8*j+:8];
    end
  end
  always @(posedge clk_i) begin
    if(!rst_ni) begin i_rsp_valid<=0;d_rsp_valid<=0;i_rsp_error<=0;d_rsp_error<=0;end
    else begin
      if(i_rsp_ready) i_rsp_valid<=0;
      if(d_rsp_ready) d_rsp_valid<=0;
      if(i_req_valid && i_req_ready) begin i_rsp_valid<=1;i_rsp_error<=i_bad;end
      if(d_req_valid && d_req_ready) begin d_rsp_valid<=1;d_rsp_error<=d_bad;end
    end
  end
endmodule
