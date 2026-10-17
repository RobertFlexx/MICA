// MICA v1.0 experimental multi-cycle synthesizable scalar core.
// Supports XLEN=32 and XLEN=64. This is NOT a pipelined, verified, production CPU.
// Instruction ROM and data RAM are asynchronous read, synchronous write.
// Unsupported extensions / illegal instructions raise fault_o and halt.
// SPDX-License-Identifier: MIT
module mica_core
    #(parameter integer XLEN = 32,
      parameter integer XREG = 0,
      parameter integer MUL = 0,
      parameter integer FLOW = 0,
      parameter integer RAM_BYTES = 65536)
    (input logic clk_i,
     input logic rst_ni,
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
  localparam integer BUS_BYTES = XLEN / 8;
  typedef enum logic [1 : 0] { FETCH0, FETCH1, EXECUTE, HALTED } state_t;
  state_t state;
  logic [XLEN - 1 : 0] pc;
  logic [15 : 0] inst_lo, inst_hi;
  logic [XLEN - 1 : 0] regs[0 : 15];
  logic [31 : 0] ir;
  logic [25 : 0] payload;
  logic [3 : 0] major;
  logic [XLEN - 1 : 0] ea;
  logic [3 : 0] memop;
  logic ismem, memwrite, memread, mem64, memflow;
  integer mbytes, byte_shift;
  logic bad_align;
  logic [XLEN - 1 : 0] mem_data;
  logic [XLEN - 1 : 0] mem_load;
  assign ir = {inst_hi, inst_lo};
  assign payload = {inst_lo[9 : 0], inst_hi};
  assign major = inst_lo[13 : 10];
  assign pc_o = pc;
  assign debug_a0_o = regs[1];
  assign halt_o = (state == HALTED);
  assign imem_addr_o = pc + ((state == FETCH1) ? XLEN'(2) : XLEN'(0));

  function automatic[XLEN - 1 : 0] rr
      (input logic [3 : 0] idx);
    begin
      if (idx == 0)
        rr = '0;
      else
        rr = regs[idx];
    end
  endfunction
  function automatic[XLEN - 1 : 0] sext
      (input logic [XLEN - 1 : 0] data,
       input integer bits);
    begin
      sext = $signed(data << (XLEN - bits)) >>> (XLEN - bits);
    end
  endfunction
  function automatic[XLEN - 1 : 0] arithmetic
      (input logic [5 : 0] op,
       input logic [XLEN - 1 : 0] a,
       input logic [XLEN - 1 : 0] b);
    integer shift_amount;
    begin
      shift_amount = b % XLEN;
      case (op)
        0:
          arithmetic = a + b;
        1:
          arithmetic = a - b;
        2:
          arithmetic = a & b;
        3:
          arithmetic = a | b;
        4:
          arithmetic = a ^ b;
        5:
          arithmetic = a << shift_amount;
        6:
          arithmetic = a >> shift_amount;
        7:
          arithmetic = $signed(a) >>> shift_amount;
        8:
          arithmetic = XLEN'($signed(a) < $signed(b));
        9:
          arithmetic = XLEN'(a < b);
        10:
          arithmetic = XLEN'(a == b);
        11:
          arithmetic = MUL ? (a * b) : '0;
        default:
          arithmetic = '0;
      endcase
    end
  endfunction

  // Memory address/size/byte-lane mux. All natural alignment is required.
  always_comb begin
    ismem = 0;
    memwrite = 0;
    memread = 0;
    mem64 = 0;
    memflow = 0;
    memop = 0;
    mbytes = 1;
    ea = '0;
    mem_data = '0;
    if (state == EXECUTE) begin
      if (inst_lo[15 : 14] == 2'b00 && inst_lo[13 : 6] >= 8'd23 &&
          inst_lo[13 : 6] <= 8'd30 && FLOW != 0) begin
        ismem = 1;
        memflow = 1;
        memop = {1'b0, inst_lo[13 : 6] - 8'd23};
        memwrite = memop >= 4;
        memread = !memwrite;
        mbytes = 1 << (memop[1 : 0]);
        ea = rr({1'b0, inst_lo[2 : 0]});
        mem_data = rr({1'b0, inst_lo[5 : 3]});
        if (inst_lo[2 : 0] == 0 || inst_lo[2 : 0] == inst_lo[5 : 3] ||
            (mbytes == 8 && XLEN != 64)) begin
          memwrite = 0;
          memread = 0;
        end
      end else if (inst_lo[15 : 14] == 2'b10) begin
        ismem = 1;
        memop = {1'b0, inst_lo[13 : 11]};
        memwrite = (memop == 1 || memop == 3 || memop == 5);
        memread = !memwrite;
        mbytes = (memop <= 1)
                     ? 4
                     : ((memop == 2 || memop == 3 || memop == 6) ? 2 : 1);
        ea = rr({1'b0, inst_lo[7 : 5]}) +
             XLEN'($signed(inst_lo[4 : 0]) * mbytes);
        mem_data = rr({1'b0, inst_lo[10 : 8]});
      end else if (inst_lo[15 : 14] == 2'b11 && major == 4'd8 && XLEN == 64)
      begin
        ismem = 1;
        mem64 = 1;
        memop = {1'b0, payload[25 : 22]};
        memwrite = (memop == 1);
        memread = !memwrite;
        mbytes = (memop <= 1)
                     ? 8
                     : ((memop == 2 || memop == 3) ? 4 : (memop == 5 ? 2 : 1));
        ea = rr(payload[17 : 14]) + XLEN'($signed(payload[13 : 0]));
        mem_data = rr(payload[21 : 18]);
        if (memop > 5) begin
          memwrite = 0;
          memread = 0;
        end
      end else if (inst_lo[15 : 14] == 2'b11 && major == 4'd10 && FLOW != 0)
      begin
        ismem = 1;
        memflow = 1;
        memop = payload[25 : 22];
        memwrite = memop >= 4 && memop <= 7;
        memread = memop < 4;
        mbytes = 1 << (memop[1 : 0]);
        ea = rr(payload[17 : 14]);
        mem_data = rr(payload[21 : 18]);
        if (memop > 7 || payload[17 : 14] == 0 ||
            payload[17 : 14] == payload[21 : 18] || (mbytes == 8 && XLEN != 64))
        begin
          memwrite = 0;
          memread = 0;
        end
      end
    end
    bad_align = is_mem_alignment_bad();
    byte_shift = integer'(ea % BUS_BYTES) * 8;
    dmem_addr_o = ea & ~(XLEN'(BUS_BYTES - 1));
    dmem_wdata_o = mem_data << byte_shift;
    dmem_wstrb_o = '0;
    if (memwrite && !bad_align)
      for (integer k = 0; k < BUS_BYTES; k = k + 1)
        if (k >= integer'(ea % BUS_BYTES) &&
            k < integer'(ea % BUS_BYTES) + mbytes)
          dmem_wstrb_o[k] = 1'b1;
    dmem_re_o = memread && !bad_align;
    dmem_we_o =
        memwrite && !bad_align &&
        (!mem64 || (memop <= 5 && (XREG != 0 || (payload[21 : 18] < 8 &&
                                                 payload[17 : 14] < 8)))) &&
        (!memflow || FLOW != 0) &&
        (!memflow || inst_lo[15 : 14] != 2'b11 || XREG != 0 ||
         (payload[21 : 18] < 8 && payload[17 : 14] < 8));
    mem_load = dmem_rdata_i >> byte_shift;
  end
  function automatic logic is_mem_alignment_bad
      ();
    begin
      is_mem_alignment_bad = (ea % mbytes) != 0;
    end
  endfunction

  always_ff @(posedge clk_i or negedge rst_ni) begin : sequential
    logic [XLEN - 1 : 0] nextpc, a, b, z;
    logic [3 : 0] d, s, t;
    logic [5 : 0] operation;
    logic take;
    logic illegal, stop_requested;
    logic [31 : 0] tmpword;
    integer i;
    if (!rst_ni) begin
      state <= FETCH0;
      pc <= '0;
      inst_lo <= 0;
      inst_hi <= 0;
      fault_o <= 0;
      for (i = 0; i < 16; i = i + 1)
        regs[i] <= '0;
      regs[7] <= XLEN'(RAM_BYTES - 16);
    end else begin
      case (state)
        FETCH0: begin
          inst_lo <= imem_rdata_i;
          if (imem_rdata_i[15 : 14] == 2'b11)
            state <= FETCH1;
          else
            state <= EXECUTE;
        end
        FETCH1: begin
          inst_hi <= imem_rdata_i;
          state <= EXECUTE;
        end
        EXECUTE: begin
          nextpc = pc + ((inst_lo[15 : 14] == 2'b11) ? XLEN'(4) : XLEN'(2));
          d = 0;
          s = 0;
          t = 0;
          a = '0;
          b = '0;
          z = '0;
          take = 0;
          operation = 0;
          illegal = 0;
          stop_requested = 0;
          tmpword = 0;
          case (inst_lo[15 : 14])
            2'b00: begin
              operation = inst_lo[13 : 6];
              d = {1'b0, inst_lo[5 : 3]};
              s = {1'b0, inst_lo[2 : 0]};
              a = rr(d);
              b = rr(s);
              if (operation == 0) begin
                if (d != 0 || s != 0)
                  illegal = 1;
              end else if (operation >= 23 && operation <= 30) begin
                if (FLOW == 0 || s == 0 || s == d || bad_align ||
                    (mbytes == 8 && XLEN != 64))
                  illegal = 1;
                else begin
                  if (memread) begin
                    case (memop)
                      0:
                        regs[d] <= mem_load & XLEN'('hff);
                      1:
                        regs[d] <= mem_load & XLEN'('hffff);
                      2:
                        regs[d] <= mem_load & XLEN'('hffffffff);
                      3:
                        regs[d] <= mem_load;
                      default:
                        illegal = 1;
                    endcase
                  end
                  regs[s] <= b + XLEN'(mbytes);
                end
              end else if (operation == 1)
                regs[d] <= b;
              else if (operation >= 2 && operation <= 12)
                regs[d] <= arithmetic(operation - 6'd2, a, b);
              else if (operation == 13 || operation == 14) begin
                if (s != 0)
                  illegal = 1;
                if (operation == 14)
                  regs[6] <= nextpc;
                nextpc = a;
              end else if (operation == 15) begin
                if (s != 0)
                  illegal = 1;
                regs[d] <= ~a;
              end else if (operation == 16) begin
                if (s != 0)
                  illegal = 1;
                regs[d] <= -a;
              end else if (operation == 17) begin
                if (MUL == 0)
                  illegal = 1;
                else
                  regs[d] <= a * b;
              end else if (operation == 18 || operation == 20) begin
                if (d != 0 || s != 0)
                  illegal = 1;
                else
                  stop_requested = 1;
              end else if (operation == 19 || operation == 22) begin
                if (d != 0 || s != 0)
                  illegal = 1;
              end else
                illegal = 1; // eret, privilege/interrupt support absent
            end
            2'b01: begin
              operation = {3'b0, inst_lo[13 : 11]};
              d = {1'b0, inst_lo[10 : 8]};
              a = rr(d);
              case (operation)
                0:
                  regs[d] <= sext(XLEN'(inst_lo[7 : 0]), 8);
                1:
                  regs[d] <= a + sext(XLEN'(inst_lo[7 : 0]), 8);
                2:
                  regs[d] <= a & XLEN'(inst_lo[7 : 0]);
                3: begin
                  if (inst_lo[7 : 5] != 0)
                    illegal = 1;
                  regs[d] <= a << inst_lo[4 : 0];
                end
                4: begin
                  if (inst_lo[7 : 5] != 0)
                    illegal = 1;
                  regs[d] <= a >> inst_lo[4 : 0];
                end
                5: begin
                  if (a == 0)
                    nextpc = nextpc + sext(XLEN'(inst_lo[7 : 0]), 8) * XLEN'(2);
                end
                6: begin
                  if (a != 0)
                    nextpc = nextpc + sext(XLEN'(inst_lo[7 : 0]), 8) * XLEN'(2);
                end
                7:
                  nextpc = nextpc + sext(XLEN'(inst_lo[10 : 0]), 11) * XLEN'(2);
                default:
                  illegal = 1;
              endcase
            end
            2'b10: begin
              d = {1'b0, inst_lo[10 : 8]};
              if (bad_align)
                illegal = 1;
              else if (memread) begin
                case (memop)
                  0:
                    regs[d] <= mem_load & XLEN'('hffffffff);
                  2:
                    regs[d] <= sext(mem_load & XLEN'('hffff), 16);
                  4:
                    regs[d] <= sext(mem_load & XLEN'('hff), 8);
                  6:
                    regs[d] <= mem_load & XLEN'('hffff);
                  7:
                    regs[d] <= mem_load & XLEN'('hff);
                  default:
                    illegal = 1;
                endcase
              end
            end
            2'b11: begin
              case (major)
                0: begin
                  operation = payload[25 : 20];
                  d = payload[19 : 16];
                  s = payload[15 : 12];
                  t = payload[11 : 8];
                  if (payload[7 : 0] != 0 || operation > 11 ||
                      ((d >= 8 || s >= 8 || t >= 8) && XREG == 0) ||
                      (operation == 11 && MUL == 0))
                    illegal = 1;
                  else
                    regs[d] <= arithmetic(operation, rr(s), rr(t));
                end
                1: begin
                  operation = {2'b0, payload[25 : 22]};
                  d = payload[21 : 18];
                  s = payload[17 : 14];
                  a = rr(s);
                  if (operation > 6 || ((d >= 8 || s >= 8) && XREG == 0))
                    illegal = 1;
                  else
                    case (operation)
                      0:
                        regs[d] <= a + sext(XLEN'(payload[13 : 0]), 14);
                      1:
                        regs[d] <= a & XLEN'(payload[13 : 0]);
                      2:
                        regs[d] <= a | XLEN'(payload[13 : 0]);
                      3:
                        regs[d] <= a ^ XLEN'(payload[13 : 0]);
                      4: begin
                        if (payload[13 : 0] >= XLEN)
                          illegal = 1;
                        else
                          regs[d] <= a << payload[5 : 0];
                      end
                      5: begin
                        if (payload[13 : 0] >= XLEN)
                          illegal = 1;
                        else
                          regs[d] <= a >> payload[5 : 0];
                      end
                      6: begin
                        if (payload[13 : 0] >= XLEN)
                          illegal = 1;
                        else
                          regs[d] <= $signed(a) >>> payload[5 : 0];
                      end
                      default:
                        illegal = 1;
                    endcase
                end
                2: begin
                  operation = payload[25 : 20];
                  d = payload[19 : 16];
                  if (operation > 2 || (d >= 8 && XREG == 0))
                    illegal = 1;
                  else if (operation == 0)
                    regs[d] <= XLEN'({payload[15 : 0], 16'b0});
                  else if (operation == 1)
                    regs[d] <=
                        (rr(d) & ~XLEN'('hffff)) | XLEN'(payload[15 : 0]);
                  else
                    regs[d] <= sext(XLEN'(payload[15 : 0]), 16);
                end
                3: begin
                  operation = {2'b0, payload[25 : 22]};
                  s = payload[21 : 18];
                  t = payload[17 : 14];
                  a = rr(s);
                  b = rr(t);
                  if (operation > 5 || ((s >= 8 || t >= 8) && XREG == 0))
                    illegal = 1;
                  else begin
                    case (operation)
                      0:
                        take = (a == b);
                      1:
                        take = (a != b);
                      2:
                        take = ($signed(a) < $signed(b));
                      3:
                        take = ($signed(a) >= $signed(b));
                      4:
                        take = (a < b);
                      5:
                        take = (a >= b);
                      default:
                        take = 0;
                    endcase
                    if (take)
                      nextpc =
                          nextpc + sext(XLEN'(payload[13 : 0]), 14) * XLEN'(2);
                  end
                end
                4: begin
                  if (payload[25 : 24] > 1)
                    illegal = 1;
                  else begin
                    if (payload[24])
                      regs[6] <= nextpc;
                    nextpc =
                        nextpc + sext(XLEN'(payload[23 : 0]), 24) * XLEN'(2);
                  end
                end
                7: begin
                  operation = payload[25 : 20];
                  d = payload[19 : 16];
                  s = payload[15 : 12];
                  t = payload[11 : 8];
                  a = rr(s);
                  b = rr(t);
                  if (XLEN != 64 || payload[7 : 0] != 0 || operation > 8 ||
                      ((d >= 8 || s >= 8 || t >= 8) && XREG == 0) ||
                      (operation == 8 && MUL == 0))
                    illegal = 1;
                  else begin
                    case (operation)
                      0:
                        tmpword = a[31 : 0] + b[31 : 0];
                      1:
                        tmpword = a[31 : 0] - b[31 : 0];
                      2:
                        tmpword = a[31 : 0] << b[4 : 0];
                      3:
                        tmpword = a[31 : 0] >> b[4 : 0];
                      4:
                        tmpword = $signed(a[31 : 0]) >>> b[4 : 0];
                      5:
                        tmpword = a[31 : 0] & b[31 : 0];
                      6:
                        tmpword = a[31 : 0] | b[31 : 0];
                      7:
                        tmpword = a[31 : 0] ^ b[31 : 0];
                      8:
                        tmpword = a[31 : 0] * b[31 : 0];
                      default:
                        tmpword = 0;
                    endcase
                    regs[d] <= sext(XLEN'(tmpword), 32);
                  end
                end
                9: begin
                  d = payload[23 : 20];
                  z = rr(d) - XLEN'(1);
                  if (FLOW == 0 || payload[25 : 24] != 0 || d == 0 ||
                      (d >= 8 && XREG == 0))
                    illegal = 1;
                  else begin
                    regs[d] <= z;
                    if (z != 0)
                      nextpc =
                          nextpc + sext(XLEN'(payload[19 : 0]), 20) * XLEN'(2);
                  end
                end
                10: begin
                  d = payload[21 : 18];
                  s = payload[17 : 14];
                  if (FLOW == 0 || memop > 7 || s == 0 || s == d || bad_align ||
                      (mbytes == 8 && XLEN != 64) ||
                      ((d >= 8 || s >= 8) && XREG == 0))
                    illegal = 1;
                  else begin
                    if (memread) begin
                      case (memop)
                        0:
                          regs[d] <= mem_load & XLEN'('hff);
                        1:
                          regs[d] <= mem_load & XLEN'('hffff);
                        2:
                          regs[d] <= mem_load & XLEN'('hffffffff);
                        3:
                          regs[d] <= mem_load;
                        default:
                          illegal = 1;
                      endcase
                    end
                    regs[s] <= rr(s) + sext(XLEN'(payload[13 : 0]), 14);
                  end
                end
                8: begin
                  d = payload[21 : 18];
                  if (XLEN != 64 || memop > 5 || bad_align ||
                      ((d >= 8 || payload[17 : 14] >= 8) && XREG == 0))
                    illegal = 1;
                  else if (memread) begin
                    case (memop)
                      0:
                        regs[d] <= mem_load;
                      2:
                        regs[d] <= sext(mem_load & XLEN'('hffffffff), 32);
                      3:
                        regs[d] <= mem_load & XLEN'('hffffffff);
                      4:
                        regs[d] <= sext(mem_load & XLEN'('hff), 8);
                      5:
                        regs[d] <= sext(mem_load & XLEN'('hffff), 16);
                      default:
                        illegal = 1;
                    endcase
                  end
                end
                default:
                  illegal = 1; // A, V, P not implemented in this small RTL
              endcase
            end
          endcase
          regs[0] <= '0;
          if (illegal || nextpc[0]) begin
            fault_o <= 1;
            state <= HALTED;
          end else if (stop_requested)
            state <= HALTED;
          else
            state <= FETCH0;
          pc <= nextpc;
        end
        HALTED: begin
          state <= HALTED;
        end
        default: begin
          state <= HALTED;
          fault_o <= 1;
        end
      endcase
    end
  end
endmodule
