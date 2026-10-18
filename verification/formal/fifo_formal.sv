// A shift-register queue is the independent reference for the circular FIFO.
// Payloads and simultaneous push/pop requests are unconstrained.
module fifo_formal(input clk_i,rst_ni,push_valid_i,pop_ready_i,input [3:0] push_data_i);
  wire push_ready_o,pop_valid_o;
  wire [3:0] pop_data_o;
  wire [1:0] level_o;
  wire push=push_valid_i && push_ready_o,pop=pop_valid_o && pop_ready_i;
  reg [3:0] first,second,third;
  reg [1:0] count=0;
  reg past_valid=0;
  mica_sync_fifo #(.WIDTH(4),.DEPTH(3)) dut(.*);
  always @(posedge clk_i) begin
    past_valid<=1;
    if(!past_valid) assume(!rst_ni);
    if(!rst_ni) count<=0;
    else begin
      assert(level_o==count);
      assert(pop_valid_o==(count!=0));
      assert(push_ready_o==((count<3) || pop));
      if(pop_valid_o) assert(pop_data_o==first);
      assert(count<=3);
      if(pop) begin first<=second;second<=third;end
      if(push) case(count-{1'b0,pop})
        0: first<=push_data_i;
        1: second<=push_data_i;
        2: third<=push_data_i;
      endcase
      case({push,pop})
        2'b10: count<=count+1;
        2'b01: count<=count-1;
      endcase
    end
  end
endmodule
