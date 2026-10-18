// Legacy zero-wait-state port adapter around the transactional reference core.
// New systems should instantiate mica_core_txn directly. SPDX-License-Identifier: MIT
module mica_core
    #(parameter integer XLEN = 32,
      parameter integer XREG = 0,
      parameter integer MUL = 0,
      parameter integer FLOW = 0,
      parameter integer BITOPS = 0,
      parameter integer TRAP = 0,
      parameter integer PERF = 0,
      parameter integer RAM_BYTES = 65536)
    (input logic clk_i,
     input logic rst_ni,
     input logic irq_i,
     output logic [XLEN - 1 : 0] imem_addr_o,
     input logic [15 : 0] imem_rdata_i,
     output logic [XLEN - 1 : 0] dmem_addr_o,
     output logic [XLEN - 1 : 0] dmem_wdata_o,
     output logic [XLEN / 8 - 1 : 0] dmem_wstrb_o,
     output logic dmem_re_o,
     output logic dmem_we_o,
     input logic [XLEN - 1 : 0] dmem_rdata_i,
     output logic halt_o,
     output logic fault_o,
     output logic [XLEN - 1 : 0] pc_o,
     output logic [XLEN - 1 : 0] debug_a0_o);
  logic iv,ir,sv,sr,dv,dr,ds,dsr,dw;
  logic [XLEN-1:0] ia,da,wd,rd,ibase;
  logic [XLEN/8-1:0] strb;
  logic [2:0] size_unused;
  logic [31:0] instruction;
  logic [1:0] if_state;
  assign ir=if_state==0;
  assign sv=if_state==2;
  assign imem_addr_o=if_state==1 ? ibase+XLEN'(2):ia;
  assign dr=!ds || dsr;
  assign dmem_addr_o=da & ~XLEN'(XLEN/8-1);
  assign dmem_wdata_o=wd;
  assign dmem_wstrb_o=strb;
  assign dmem_re_o=dv && dr && !dw;
  assign dmem_we_o=dv && dr && dw;
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if(!rst_ni) begin if_state<=0;ibase<=0;instruction<=0;ds<=0;rd<=0;end
    else begin
      case(if_state)
      0:if(iv) begin instruction[15:0]<=imem_rdata_i;ibase<=ia;if_state<=1;end
      1:begin instruction[31:16]<=imem_rdata_i;if_state<=2;end
      2:if(sr) if_state<=0;
      default:if_state<=0;
      endcase
      if(dsr) ds<=0;
      if(dv && dr) begin rd<=dmem_rdata_i;ds<=1;end
    end
  end
  mica_core_txn #(.XLEN(XLEN),.XREG(XREG),.MUL(MUL),.FLOW(FLOW),.BITOPS(BITOPS),
    .TRAP(TRAP),.PERF(PERF),.RAM_BYTES(RAM_BYTES)) reference_core (
    .clk_i(clk_i),.rst_ni(rst_ni),.irq_i(irq_i),
    .i_req_valid(iv),.i_req_ready(ir),.i_req_addr(ia),.i_rsp_valid(sv),.i_rsp_ready(sr),
    .i_rsp_rdata(instruction),.i_rsp_error(1'b0),
    .d_req_valid(dv),.d_req_ready(dr),.d_req_addr(da),.d_req_write(dw),.d_req_size(size_unused),
    .d_req_wdata(wd),.d_req_wstrb(strb),.d_rsp_valid(ds),.d_rsp_ready(dsr),.d_rsp_rdata(rd),.d_rsp_error(1'b0),
    .halt_o(halt_o),.fault_o(fault_o),.pc_o(pc_o),.debug_a0_o(debug_a0_o),
    .trace_valid(),.trace_retired(),.trace_trap(),.trace_order(),.trace_pc(),.trace_next_pc(),
    .trace_cause(),.trace_insn(),.trace_length(),.trace_regs(),.trace_mem_valid(),.trace_mem_write(),
    .trace_mem_addr(),.trace_mem_data(),.trace_mem_bytes());
endmodule
