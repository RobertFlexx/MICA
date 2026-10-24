// MICA 32/64 transactional multicycle reference core. SPDX-License-Identifier: MIT
// One request per port outstanding. Reset cancels both ports with the fabric.
module mica_core_txn
    #(parameter integer XLEN = 32, XREG = 0, MUL = 0, FLOW = 0, BITOPS = 0,
      parameter integer TRAP = 0, PERF = 1, MICA2 = 0, RAM_BYTES = 65536,
                        FETCH_REUSE = 1, FETCH_SELECTIVE = 1, FAST_FETCH = 1,
                        REG_PARITY = 0)
    (input logic clk_i, irq_i,
     // Assertions sample reset to disable checks; architectural reset is asynchronous.
     /* verilator lint_off SYNCASYNCNET */
     input logic rst_ni,
     /* verilator lint_on SYNCASYNCNET */
     output logic i_req_valid,
     input logic i_req_ready,
     output logic [XLEN - 1 : 0] i_req_addr,
     input logic i_rsp_valid,
     output logic i_rsp_ready,
     input logic [31 : 0] i_rsp_rdata,
     input logic i_rsp_error,
     output logic d_req_valid,
     input logic d_req_ready,
     output logic [XLEN - 1 : 0] d_req_addr,
     output logic d_req_write,
     output logic [2 : 0] d_req_size,
     output logic [XLEN - 1 : 0] d_req_wdata,
     output logic [XLEN / 8 - 1 : 0] d_req_wstrb,
     input logic d_rsp_valid,
     output logic d_rsp_ready,
     input logic [XLEN - 1 : 0] d_rsp_rdata,
     input logic d_rsp_error,
     output logic halt_o, fault_o,
     output logic [XLEN - 1 : 0] pc_o, debug_a0_o,
     output logic trace_valid, trace_retired, trace_trap,
     output logic [63 : 0] trace_order,
     output logic [XLEN - 1 : 0] trace_pc, trace_next_pc, trace_cause,
     output logic [31 : 0] trace_insn,
     output logic [2 : 0] trace_length,
     output logic [16 * XLEN - 1 : 0] trace_regs,
     output logic trace_mem_valid, trace_mem_write,
     output logic [XLEN - 1 : 0] trace_mem_addr, trace_mem_data,
     output logic [3 : 0] trace_mem_bytes);
`include "mica_isa.svh"
  localparam integer NR = XREG != 0 ? 16 : 8;
  localparam integer BUS_BYTES = XLEN / 8;
  localparam [XLEN - 1 : 0] FEATURES = XLEN'(
                                (XREG != 0 ? 1 : 0) | (MUL != 0 ? 2 : 0) |
                                (FLOW != 0 ? 4 : 0) | (BITOPS != 0 ? 32 : 0) |
                                (TRAP != 0 ? 64 : 0) | (PERF != 0 ? 128 : 0) |
                                (MICA2 != 0 ? 256 : 0));
  typedef enum logic [3 : 0] {
    START,
    LOOKUP,
    IREQ,
    IWAIT,
    PARCEL,
    DECODE,
    DREQ,
    DWAIT,
    COMMIT,
    SLEEP,
    STOP
  } state_t;
  state_t state;
  logic [XLEN - 1 : 0] regs[0 : NR - 1];
  wire register_error;
  logic [XLEN - 1 : 0] pc, fetch_addr, cache_tag;
  logic [31 : 0] cache_data, parcel_word;
  logic cache_valid, second;
  logic [15 : 0] lo, hi;
  wire [25 : 0] p = {lo[9 : 0], hi};
  wire [3 : 0] major = lo[13 : 10];
  wire [2 : 0] ilen = lo[15 : 14] == 3 ? 3'd4 : 3'd2;
  logic [XLEN - 1 : 0] status_reg, epc_reg, cause_reg, tval_reg, tvec_reg,
                       ie_reg, ip_reg;
  logic [63 : 0] cycle_count, instret, timer_count, timer_cmp, order_count;
  wire [XLEN - 1 : 0] pending =
                          ip_reg | XLEN'(irq_i) |
                          (timer_count >= timer_cmp ? XLEN'(2) : XLEN'(0));
  wire interrupt_ready = TRAP != 0 && status_reg[0] && (ie_reg & pending) != 0;
  wire [XLEN - 1 : 0] interrupt_cause =
                          (XLEN'(1) << (XLEN - 1)) |
                          (((ie_reg & pending & XLEN'(2)) != 0) ? XLEN'(2)
                                                                : XLEN'(1));

  function automatic[XLEN - 1 : 0] rr
      (input logic [3 : 0] idx);
    rr = (idx == 0 || int'(idx) >= NR) ? '0 : regs[idx[$clog2(NR) - 1 : 0]];
  endfunction
  function automatic logic valid_reg
      (input logic [3 : 0] idx);
    valid_reg = int'(idx) < NR;
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
      shift_amount = int'(b & XLEN'(XLEN - 1));
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
          arithmetic = (MUL != 0) ? (a * b) : '0;
        default:
          arithmetic = '0;
      endcase
    end
  endfunction

  // Optional B datapath. Variable rotate and population counts are combinational
  // in the reference core; critical path should be measured after synthesis.
  function automatic[XLEN - 1 : 0] bit_arithmetic
      (input logic [5 : 0] op,
       input logic [XLEN - 1 : 0] a,
       input logic [XLEN - 1 : 0] b);
    integer k, shift_amount;
    logic [XLEN - 1 : 0] result, selector;
    begin
      result = '0;
      shift_amount = integer'(b & XLEN'(XLEN - 1));
      selector = XLEN'(1) << shift_amount;
      case (op)
        0: begin
          result = XLEN'(XLEN);
          for (k = XLEN - 1; k >= 0; k = k - 1)
            if (a[k] && result == XLEN'(XLEN))
              result = XLEN'(int'(XLEN - 1 - k));
        end
        1: begin
          result = XLEN'(XLEN);
          for (k = 0; k < XLEN; k = k + 1)
            if (a[k] && result == XLEN'(XLEN))
              result = XLEN'(k);
        end
        2: begin
          for (k = 0; k < XLEN; k = k + 1)
            result = result + XLEN'(a[k]);
        end
        3: begin
          for (k = 0; k < XLEN / 8; k = k + 1)
            result[8 * k +: 8] = a[XLEN - 8 - 8 * k +: 8];
        end
        4:
          result = (a >> shift_amount) | (a << ((XLEN - shift_amount) % XLEN));
        5:
          result = (a << shift_amount) | (a >> ((XLEN - shift_amount) % XLEN));
        6:
          result = ($signed(a) < $signed(b)) ? a : b;
        7:
          result = ($signed(a) > $signed(b)) ? a : b;
        8:
          result = (a < b) ? a : b;
        9:
          result = (a > b) ? a : b;
        10:
          result = a | selector;
        11:
          result = a & ~selector;
        12:
          result = a ^ selector;
        13:
          result = (a >> shift_amount) & XLEN'(1);
        14:
          result = a & ~b;
        15:
          result = a | ~b;
        16:
          result = ~(a ^ b);
        17:
          result = sext(XLEN'(a[7 : 0]), 8);
        18:
          result = sext(XLEN'(a[15 : 0]), 16);
        19:
          result = XLEN'(a[15 : 0]);
        default:
          result = '0;
      endcase
      bit_arithmetic = result;
    end
  endfunction

  logic illegal, mem, memwrite, memsign, w1, w2, csrwrite, do_ecall, do_eret,
        stop_requested, wait_requested;
  logic invalidate;
  logic [3 : 0] dst1, dst2;
  logic [7 : 0] csr_id;
  logic [XLEN - 1 : 0] value1, value2, nextpc, addr, store_data, csr_value;
  logic [2 : 0] size_log;
  logic [XLEN - 1 : 0] decoded_cause, decoded_tval;
  logic [XLEN - 1 : 0] q_value1, q_value2, q_nextpc, q_addr, q_store,
                       q_csr_value;
  logic [3 : 0] q_dst1, q_dst2;
  logic q_w1, q_w2, q_mem, q_memwrite, q_memsign, q_csrwrite, q_ecall, q_eret,
        q_stop, q_wait, q_invalidate;
  logic [2 : 0] q_size;
  logic [7 : 0] q_csr;
  logic [XLEN - 1 : 0] response_data;
  wire [XLEN - 1 : 0] writeback_value =
                          q_mem ? (q_memsign
                                       ? sext(response_data, 8 * (1 << q_size))
                                       : response_data &
                                             ({XLEN{1'b1}} >>
                                              (XLEN - 8 * (1 << q_size))))
                                : q_value1;
  generate
    if (REG_PARITY != 0) begin : parity
      logic [NR - 1 : 0] bits;
      wire [NR - 1 : 0] errors;
      for (genvar r = 0; r < NR; r = r + 1) begin : check_register
        assign errors[r] = (^regs[r]) != bits[r];
      end
      assign register_error = |errors;
      always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
          bits <= '0;
          bits[7] <= ^XLEN'(int'((RAM_BYTES - 16) & ~15));
        end else begin
          bits[0] <= 0;
          if (state == COMMIT && !q_ecall) begin
            if (q_w1 && q_dst1 != 0)
              bits[q_dst1[$clog2(NR) - 1 : 0]] <= ^writeback_value;
            if (q_w2 && q_dst2 != 0)
              bits[q_dst2[$clog2(NR) - 1 : 0]] <= ^q_value2;
          end
        end
      end
    end else begin : no_parity
      assign register_error = 0;
    end
  endgenerate

  assign halt_o = state == STOP;
  assign pc_o = pc;
  assign debug_a0_o = regs[1];
  assign i_req_valid = rst_ni && state == IREQ;
  assign i_req_addr = fetch_addr & ~XLEN'(3);
  assign i_rsp_ready = rst_ni && state == IWAIT;
  assign d_req_valid = rst_ni && state == DREQ;
  assign d_req_addr = q_addr;
  assign d_req_write = q_memwrite;
  assign d_req_size = q_size;
  assign d_req_wdata = q_store << (8 * int'(q_addr & XLEN'(BUS_BYTES - 1)));
  assign d_req_wstrb = q_memwrite
                           ? (({BUS_BYTES{1'b1}} >> (BUS_BYTES - (1 << q_size)))
                              << int'(q_addr & XLEN'(BUS_BYTES - 1)))
                           : '0;
  assign d_rsp_ready = rst_ni && state == DWAIT;
  generate
    for (genvar r = 0; r < 16; r = r + 1) begin : debug_registers
      if (r < NR) begin : present
        assign trace_regs[r * XLEN +: XLEN] = r == 0 ? {XLEN{1'b0}} : regs[r];
      end else begin : absent
        assign trace_regs[r * XLEN +: XLEN] = '0;
      end
    end
  endgenerate

  always_comb begin : decode
    logic [3 : 0] d, a, b;
    logic [7 : 0] op;
    logic [XLEN - 1 : 0] av, bv;
    logic take;
    logic [31 : 0] word_result;
    integer bytes;
    illegal = 0;
    mem = 0;
    memwrite = 0;
    memsign = 0;
    w1 = 0;
    w2 = 0;
    csrwrite = 0;
    do_ecall = 0;
    do_eret = 0;
    stop_requested = 0;
    wait_requested = 0;
    invalidate = 0;
    dst1 = 0;
    dst2 = 0;
    value1 = 0;
    value2 = 0;
    addr = 0;
    store_data = 0;
    size_log = 0;
    csr_id = 0;
    csr_value = 0;
    nextpc = pc + XLEN'(ilen);
    decoded_cause = XLEN'(2);
    decoded_tval = XLEN'({hi, lo});
    d = 0;
    a = 0;
    b = 0;
    op = 0;
    av = 0;
    bv = 0;
    take = 0;
    word_result = 0;
    bytes = 1;
    case (lo[15 : 14])
      0: begin
        op = lo[13 : 6];
        d = {1'b0, lo[5 : 3]};
        a = {1'b0, lo[2 : 0]};
        av = rr(d);
        bv = rr(a);
        dst1 = d;
        value1 = av;
        if (op >= 23 && op <= 30) begin
          illegal = FLOW == 0 || a == 0 || a == d ||
                    ((op == 26 || op == 30) && XLEN != 64);
          mem = 1;
          memwrite = op >= 27;
          size_log = 3'((int'(op) - 23) & 3);
          addr = bv;
          store_data = av;
          w1 = !memwrite;
          w2 = 1;
          dst2 = a;
          value2 = bv + XLEN'(1 << size_log);
        end else if (MICA2 != 0 && (op == 31 || op == 32)) begin
          mem = 1;
          memwrite = op == 32;
          size_log = XLEN == 64 ? 3'd3 : 3'd2;
          addr = rr(4'd7) + (XLEN'(a) << (XLEN == 64 ? 3 : 2));
          store_data = av;
          w1 = op == 31;
        end else if (MICA2 != 0 && op >= 33 && op <= 40) begin
          illegal = d == 0;
          w1 = 1;
          value1 = av - XLEN'(1);
          if (value1 != 0)
            nextpc =
                nextpc +
                sext(((XLEN'(op) - XLEN'(33)) << 3) | XLEN'(a), 6) * XLEN'(2);
        end else if (MICA2 != 0 && op == 41) begin
          illegal = d != 0 || a != 0;
          stop_requested = 1;
        end else if (op == 0)
          illegal = (d != 0 || a != 0);
        else if (op == 1) begin
          w1 = 1;
          value1 = bv;
        end else if (op >= 2 && op <= 12) begin
          w1 = 1;
          value1 = arithmetic(6'(op - 2), av, bv);
        end else if (op == 13 || op == 14) begin
          illegal = a != 0;
          nextpc = av;
          if (op == 14) begin
            w1 = 1;
            dst1 = 6;
            value1 = pc + XLEN'(2);
          end
        end else if (op == 15 || op == 16) begin
          illegal = a != 0;
          w1 = 1;
          value1 = op == 15 ? ~av : -av;
        end else if (op == 17) begin
          illegal = MUL == 0;
          w1 = 1;
          value1 = MUL != 0 ? av * bv : '0;
        end else if (op >= 18 && op <= 22) begin
          illegal = d != 0 || a != 0;
          case (op)
            18:
              if (MICA2 != 0)
                wait_requested = 1;
              else
                stop_requested = 1;
            19: begin
            end
            20:
              if (TRAP != 0)
                do_ecall = 1;
              else
                stop_requested = 1;
            21: begin
              do_eret = TRAP != 0;
              illegal = illegal || TRAP == 0 || !status_reg[2];
              nextpc = epc_reg;
            end
            22:
              invalidate = 1;
            default:
              illegal = 1;
          endcase
        end else
          illegal = 1;
      end
      1: begin
        op = {5'b0, lo[13 : 11]};
        d = {1'b0, lo[10 : 8]};
        av = rr(d);
        dst1 = d;
        w1 = op < 5;
        case (op)
          0:
            value1 = sext(XLEN'(lo[7 : 0]), 8);
          1:
            value1 = av + sext(XLEN'(lo[7 : 0]), 8);
          2:
            value1 = av & XLEN'(lo[7 : 0]);
          3: begin
            illegal = lo[7 : 5] != 0;
            value1 = av << lo[4 : 0];
          end
          4: begin
            illegal = lo[7 : 5] != 0;
            value1 = av >> lo[4 : 0];
          end
          5:
            if (av == 0)
              nextpc = nextpc + sext(XLEN'(lo[7 : 0]), 8) * XLEN'(2);
          6:
            if (av != 0)
              nextpc = nextpc + sext(XLEN'(lo[7 : 0]), 8) * XLEN'(2);
          7:
            nextpc = nextpc + sext(XLEN'(lo[10 : 0]), 11) * XLEN'(2);
          default:
            illegal = 1;
        endcase
      end
      2: begin
        op = {5'b0, lo[13 : 11]};
        d = {1'b0, lo[10 : 8]};
        a = {1'b0, lo[7 : 5]};
        size_log =
            (op <= 1) ? 3'd2 : ((op == 2 || op == 3 || op == 6) ? 3'd1 : 3'd0);
        mem = 1;
        memwrite = op == 1 || op == 3 || op == 5;
        memsign = op == 2 || op == 4 || (op == 0 && MICA2 != 0 && XLEN == 64);
        addr = rr(a) + (sext(XLEN'(lo[4 : 0]), 5) << size_log);
        store_data = rr(d);
        w1 = !memwrite;
        dst1 = d;
      end
      3: begin
        op = {2'b0, p[25 : 20]};
        d = p[19 : 16];
        a = p[15 : 12];
        b = p[11 : 8];
        av = rr(a);
        bv = rr(b);
        dst1 = d;
        case (major)
          MICA_MAJOR_ALU, MICA_MAJOR_W32, MICA_MAJOR_BITOPS: begin
            illegal = p[7 : 0] != 0 || !valid_reg(d) || !valid_reg(a) ||
                      !valid_reg(b);
            w1 = 1;
            if (major == MICA_MAJOR_ALU) begin
              illegal = illegal || op > 11 || (op == 11 && MUL == 0);
              value1 = arithmetic(6'(op), av, bv);
            end else if (major == MICA_MAJOR_BITOPS) begin
              illegal = illegal || BITOPS == 0 || op > 19 ||
                        ((op <= 3 || op >= 17) && b != 0);
              value1 = BITOPS != 0 ? bit_arithmetic(6'(op), av, bv) : '0;
            end else begin
              illegal =
                  illegal || XLEN != 64 || op > 8 || (op == 8 && MUL == 0);
              if (XLEN == 64) begin
                case (op)
                  0:
                    word_result = av[31 : 0] + bv[31 : 0];
                  1:
                    word_result = av[31 : 0] - bv[31 : 0];
                  2:
                    word_result = av[31 : 0] << bv[4 : 0];
                  3:
                    word_result = av[31 : 0] >> bv[4 : 0];
                  4:
                    word_result = $signed(av[31 : 0]) >>> bv[4 : 0];
                  5:
                    word_result = av[31 : 0] & bv[31 : 0];
                  6:
                    word_result = av[31 : 0] | bv[31 : 0];
                  7:
                    word_result = av[31 : 0] ^ bv[31 : 0];
                  8:
                    word_result = MUL != 0 ? av[31 : 0] * bv[31 : 0] : 32'b0;
                  default:
                    word_result = 0;
                endcase
              end
              value1 = sext(XLEN'(word_result), 32);
            end
          end
          MICA_MAJOR_IMM: begin
            op = {4'b0, p[25 : 22]};
            d = p[21 : 18];
            a = p[17 : 14];
            av = rr(a);
            dst1 = d;
            w1 = 1;
            illegal = op > 6 || !valid_reg(d) || !valid_reg(a) ||
                      (op >= 4 && int'(p[13 : 0]) >= XLEN);
            case (op)
              0:
                value1 = av + sext(XLEN'(p[13 : 0]), 14);
              1:
                value1 = av & XLEN'(p[13 : 0]);
              2:
                value1 = av | XLEN'(p[13 : 0]);
              3:
                value1 = av ^ XLEN'(p[13 : 0]);
              4:
                value1 = av << p[5 : 0];
              5:
                value1 = av >> p[5 : 0];
              6:
                value1 = $signed(av) >>> p[5 : 0];
              default:
                value1 = 0;
            endcase
          end
          MICA_MAJOR_WIDE: begin
            illegal = op > 3 || (op == 3 && MICA2 == 0) || !valid_reg(d);
            w1 = 1;
            case (op)
              0:
                value1 = XLEN'({p[15 : 0], 16'b0});
              1:
                value1 = (rr(d) & ~XLEN'(65535)) | XLEN'(p[15 : 0]);
              2:
                value1 = sext(XLEN'(p[15 : 0]), 16);
              3:
                value1 = pc + sext(XLEN'(p[15 : 0]), 16) * XLEN'(2);
              default:
                value1 = 0;
            endcase
          end
          MICA_MAJOR_BR: begin
            op = {4'b0, p[25 : 22]};
            a = p[21 : 18];
            b = p[17 : 14];
            av = rr(a);
            bv = rr(b);
            illegal = op > 5 || !valid_reg(a) || !valid_reg(b);
            case (op)
              0:
                take = av == bv;
              1:
                take = av != bv;
              2:
                take = $signed(av) < $signed(bv);
              3:
                take = $signed(av) >= $signed(bv);
              4:
                take = av < bv;
              5:
                take = av >= bv;
              default:
                take = 0;
            endcase
            if (take)
              nextpc = nextpc + sext(XLEN'(p[13 : 0]), 14) * XLEN'(2);
          end
          MICA_MAJOR_J: begin
            illegal = p[25 : 24] > 1;
            if (p[24]) begin
              w1 = 1;
              dst1 = 6;
              value1 = nextpc;
            end
            nextpc = nextpc + sext(XLEN'(p[23 : 0]), 24) * XLEN'(2);
          end
          MICA_MAJOR_LOOP: begin
            d = p[23 : 20];
            illegal = FLOW == 0 || p[25 : 24] != 0 || d == 0 || !valid_reg(d);
            w1 = 1;
            dst1 = d;
            value1 = rr(d) - XLEN'(1);
            if (value1 != 0)
              nextpc = nextpc + sext(XLEN'(p[19 : 0]), 20) * XLEN'(2);
          end
          MICA_MAJOR_FLOW, MICA_MAJOR_MX: begin
            op = {4'b0, p[25 : 22]};
            d = p[21 : 18];
            a = p[17 : 14];
            addr = rr(a);
            store_data = rr(d);
            dst1 = d;
            mem = 1;
            illegal = !valid_reg(d) || !valid_reg(a);
            if (major == MICA_MAJOR_FLOW) begin
              illegal = illegal || FLOW == 0 || op > 10 || a == 0 || a == d ||
                        (op >= 8 && MICA2 == 0) ||
                        (op < 8 && (op & 3) == 3 && XLEN != 64);
              size_log = op >= 8 ? 3'(op - 8) : 3'(op & 3);
              memwrite = op >= 4 && op < 8;
              memsign = op >= 8;
              w2 = 1;
              dst2 = a;
              value2 = rr(a) + sext(XLEN'(p[13 : 0]), 14);
            end else begin
              illegal = illegal || XLEN != 64 || op > 5;
              size_log =
                  op <= 1 ? 3'd3 : (op <= 3 ? 3'd2 : (op == 5 ? 3'd1 : 3'd0));
              memwrite = op == 1;
              memsign = op == 2 || op == 4 || op == 5;
              addr = addr + sext(XLEN'(p[13 : 0]), 14);
            end
            w1 = !memwrite;
          end
          MICA_MAJOR_SYS: begin
            csr_id = p[7 : 0];
            csr_value = av;
            illegal =
                (op > 1) || !valid_reg(d) || !valid_reg(a) || !valid_reg(b);
            if (op == 0) begin
              illegal = illegal || a != 0 || b != 0;
              w1 = 1;
              case (csr_id)
                MICA_CSR_COREID:
                  value1 = 0;
                MICA_CSR_FEATURES:
                  value1 = FEATURES;
                MICA_CSR_ARCH:
                  value1 = XLEN'(XLEN);
                MICA_CSR_CYCLE_LO:
                  value1 = PERF != 0 ? XLEN'(cycle_count[31 : 0]) : '0;
                MICA_CSR_CYCLE_HI:
                  value1 = PERF != 0 ? XLEN'(cycle_count[63 : 32]) : '0;
                MICA_CSR_INSTRET_LO:
                  value1 = PERF != 0 ? XLEN'(instret[31 : 0]) : '0;
                MICA_CSR_INSTRET_HI:
                  value1 = PERF != 0 ? XLEN'(instret[63 : 32]) : '0;
                default: begin
                  illegal = illegal || TRAP == 0;
                  case (csr_id)
                    MICA_CSR_STATUS:
                      value1 = status_reg;
                    MICA_CSR_EPC:
                      value1 = epc_reg;
                    MICA_CSR_CAUSE:
                      value1 = cause_reg;
                    MICA_CSR_TVEC:
                      value1 = tvec_reg;
                    MICA_CSR_IE:
                      value1 = ie_reg;
                    MICA_CSR_IP:
                      value1 = pending;
                    MICA_CSR_TIMER_LO:
                      value1 = XLEN'(timer_count[31 : 0]);
                    MICA_CSR_TIMER_HI:
                      value1 = XLEN'(timer_count[63 : 32]);
                    MICA_CSR_CMP_LO:
                      value1 = XLEN'(timer_cmp[31 : 0]);
                    MICA_CSR_CMP_HI:
                      value1 = XLEN'(timer_cmp[63 : 32]);
                    MICA_CSR_TVAL:
                      value1 = tval_reg;
                    default:
                      illegal = 1;
                  endcase
                end
              endcase
            end else if (op == 1) begin
              csrwrite = TRAP != 0;
              illegal = illegal || d != 0 || b != 0 || TRAP == 0;
              case (csr_id)
                MICA_CSR_STATUS, MICA_CSR_CAUSE, MICA_CSR_IE, MICA_CSR_IP,
                    MICA_CSR_TIMER_LO, MICA_CSR_TIMER_HI, MICA_CSR_CMP_LO,
                    MICA_CSR_CMP_HI, MICA_CSR_TVAL: begin
                end
                MICA_CSR_EPC, MICA_CSR_TVEC:
                  illegal = illegal || av[0];
                default:
                  illegal = 1;
              endcase
            end
          end
          default:
            illegal = 1;
        endcase
      end
      default:
        illegal = 1;
    endcase
    bytes = 1 << size_log;
    if (!illegal && mem && (addr & XLEN'(bytes - 1)) != 0) begin
      illegal = 1;
      decoded_cause = memwrite ? XLEN'(6) : XLEN'(4);
      decoded_tval = addr;
    end
    if (!illegal && nextpc[0]) begin
      illegal = 1;
      decoded_cause = 0;
      decoded_tval = nextpc;
    end
  end

  task automatic event_trace
      (input logic completed, trapped,
       input logic [XLEN - 1 : 0] reason, destination,
       input logic interrupt_event);
    begin
      trace_valid <= 1;
      trace_retired <= completed;
      trace_trap <= trapped;
      trace_order <= order_count;
      order_count <= order_count + 64'd1;
      trace_pc <= pc;
      trace_next_pc <= destination;
      trace_cause <= reason;
      trace_insn <= interrupt_event ? 32'b0 : {hi, lo};
      trace_length <=
          (interrupt_event || (state == IWAIT && !second) || state == START)
              ? 3'b0
              : ilen;
      trace_mem_valid <= completed && q_mem;
      trace_mem_write <= q_memwrite;
      trace_mem_addr <= q_addr;
      trace_mem_bytes <= 4'(1 << q_size);
      trace_mem_data <= (q_memwrite ? q_store : response_data) &
                        ({XLEN{1'b1}} >> (XLEN - 8 * (1 << q_size)));
    end
  endtask
  task automatic trap_entry
      (input logic [XLEN - 1 : 0] reason, saved_pc, value,
       input logic completed, interrupt_event);
    begin
      if (TRAP == 0 || status_reg[2] || tvec_reg == 0 || tvec_reg[0] ||
          tvec_reg >= XLEN'(RAM_BYTES)) begin
        fault_o <= 1;
        state <= STOP;
        event_trace(0, 1, reason, pc, interrupt_event);
      end else begin
        epc_reg <= saved_pc;
        cause_reg <= reason;
        tval_reg <= value;
        status_reg <= (status_reg & ~XLEN'(7)) |
                      (status_reg[0] ? XLEN'(2) : XLEN'(0)) | XLEN'(4);
        pc <= tvec_reg;
        state <= START;
        cache_valid <= 0;
        event_trace(completed, 1, reason, tvec_reg, interrupt_event);
        if (completed && PERF != 0)
          instret <= instret + 64'd1;
      end
    end
  endtask

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state <= START;
      pc <= 0;
      fetch_addr <= 0;
      second <= 0;
      lo <= 0;
      hi <= 0;
      cache_valid <= 0;
      cache_tag <= 0;
      cache_data <= 0;
      parcel_word <= 0;
      fault_o <= 0;
      status_reg <= 0;
      epc_reg <= 0;
      cause_reg <= 0;
      tval_reg <= 0;
      tvec_reg <= 0;
      ie_reg <= 0;
      ip_reg <= 0;
      cycle_count <= 0;
      instret <= 0;
      timer_count <= 0;
      timer_cmp <= 64'hffffffffffffffff;
      order_count <= 0;
      q_value1 <= 0;
      q_value2 <= 0;
      q_nextpc <= 0;
      q_addr <= 0;
      q_store <= 0;
      q_csr_value <= 0;
      q_dst1 <= 0;
      q_dst2 <= 0;
      q_w1 <= 0;
      q_w2 <= 0;
      q_mem <= 0;
      q_memwrite <= 0;
      q_memsign <= 0;
      q_csrwrite <= 0;
      q_ecall <= 0;
      q_eret <= 0;
      q_stop <= 0;
      q_wait <= 0;
      q_invalidate <= 0;
      q_size <= 0;
      q_csr <= 0;
      response_data <= 0;
      trace_valid <= 0;
      trace_retired <= 0;
      trace_trap <= 0;
      trace_order <= 0;
      trace_pc <= 0;
      trace_next_pc <= 0;
      trace_cause <= 0;
      trace_insn <= 0;
      trace_length <= 0;
      trace_mem_valid <= 0;
      trace_mem_write <= 0;
      trace_mem_addr <= 0;
      trace_mem_data <= 0;
      trace_mem_bytes <= 0;
      for (integer r = 0; r < NR; r = r + 1)
        regs[r] <= 0;
      regs[7] <= XLEN'(int'((RAM_BYTES - 16) & ~15));
    end else begin
      trace_valid <= 0;
      if (PERF != 0 && state != STOP)
        cycle_count <= cycle_count + 64'd1;
      if (TRAP != 0 && state != STOP)
        timer_count <= timer_count + 64'd1;
      case (state)
        START: begin
          q_mem <= 0;
          lo <= 0;
          hi <= 0;
          if (interrupt_ready)
            trap_entry(interrupt_cause, pc, 0, 0, 1);
          else if (pc[0])
            trap_entry(0, pc, pc, 0, 0);
          else begin
            fetch_addr <= pc;
            second <= 0;
            state <= LOOKUP;
          end
        end
        LOOKUP:
          if (FETCH_REUSE != 0 && cache_valid &&
              cache_tag == (fetch_addr & ~XLEN'(3))) begin
            parcel_word <= cache_data;
            state <= PARCEL;
          end else
            state <= IREQ;
        IREQ:
          if (i_req_ready)
            state <= IWAIT;
        IWAIT:
          if (i_rsp_valid) begin
            if (i_rsp_error)
              trap_entry(XLEN'(1), pc, fetch_addr, 0, 0);
            else begin
              cache_valid <= 1;
              cache_tag <= fetch_addr & ~XLEN'(3);
              cache_data <= i_rsp_rdata;
              parcel_word <= i_rsp_rdata;
              state <= PARCEL;
            end
          end
        PARCEL: begin
          if (second) begin
            hi <= fetch_addr[1] ? parcel_word[31 : 16] : parcel_word[15 : 0];
            state <= DECODE;
          end else begin
            lo <= fetch_addr[1] ? parcel_word[31 : 16] : parcel_word[15 : 0];
            hi <= 0;
            if ((fetch_addr[1] ? parcel_word[31 : 30] : parcel_word[15 : 14]) ==
                2'b11) begin
              if (FAST_FETCH != 0 && !fetch_addr[1]) begin
                hi <= parcel_word[31 : 16];
                state <= DECODE;
              end else begin
                second <= 1;
                fetch_addr <= pc + XLEN'(2);
                state <= LOOKUP;
              end
            end else
              state <= DECODE;
          end
        end
        DECODE: begin
          if (register_error) begin
            // Integrity failure is fail-stop; recovery belongs to the system.
            fault_o <= 1;
            cache_valid <= 0;
            state <= STOP;
          end else if (illegal)
            trap_entry(decoded_cause, pc, decoded_tval, 0, 0);
          else begin
            q_w1 <= w1;
            q_w2 <= w2;
            q_dst1 <= dst1;
            q_dst2 <= dst2;
            q_value1 <= value1;
            q_value2 <= value2;
            q_nextpc <= nextpc;
            q_mem <= mem;
            q_memwrite <= memwrite;
            q_memsign <= memsign;
            q_addr <= addr;
            q_store <= store_data;
            q_size <= size_log;
            q_csrwrite <= csrwrite;
            q_csr <= csr_id;
            q_csr_value <= csr_value;
            q_ecall <= do_ecall;
            q_eret <= do_eret;
            q_stop <= stop_requested;
            q_wait <= wait_requested;
            q_invalidate <= invalidate;
            if (mem)
              state <= DREQ;
            else
              state <= COMMIT;
          end
        end
        DREQ:
          if (d_req_ready)
            state <= DWAIT;
        DWAIT:
          if (d_rsp_valid) begin
            if (d_rsp_error)
              trap_entry(q_memwrite ? XLEN'(7) : XLEN'(5), pc, q_addr, 0, 0);
            else begin
              response_data <=
                  d_rsp_rdata >> (8 * int'(q_addr & XLEN'(BUS_BYTES - 1)));
              state <= COMMIT;
            end
          end
        COMMIT: begin
          if (q_ecall)
            trap_entry(XLEN'(11), MICA2 != 0 ? pc : q_nextpc, 0, 1, 0);
          else begin
            if (q_w1 && q_dst1 != 0) begin
              regs[q_dst1[$clog2(NR) - 1 : 0]] <= writeback_value;
            end
            if (q_w2 && q_dst2 != 0)
              regs[q_dst2[$clog2(NR) - 1 : 0]] <= q_value2;
            if (q_csrwrite)
              case (q_csr)
                MICA_CSR_STATUS:
                  status_reg <=
                      (status_reg & ~XLEN'(1)) | (q_csr_value & XLEN'(1));
                MICA_CSR_EPC:
                  epc_reg <= q_csr_value;
                MICA_CSR_CAUSE:
                  cause_reg <= q_csr_value;
                MICA_CSR_TVEC:
                  tvec_reg <= q_csr_value;
                MICA_CSR_IE:
                  ie_reg <= q_csr_value & XLEN'(3);
                MICA_CSR_IP:
                  ip_reg <= q_csr_value & XLEN'(1);
                MICA_CSR_TIMER_LO:
                  timer_count[31 : 0] <= q_csr_value[31 : 0];
                MICA_CSR_TIMER_HI:
                  timer_count[63 : 32] <= q_csr_value[31 : 0];
                MICA_CSR_CMP_LO:
                  timer_cmp[31 : 0] <= q_csr_value[31 : 0];
                MICA_CSR_CMP_HI:
                  timer_cmp[63 : 32] <= q_csr_value[31 : 0];
                MICA_CSR_TVAL:
                  tval_reg <= q_csr_value;
                default: begin
                end
              endcase
            if (q_eret)
              status_reg <= (status_reg & ~XLEN'(7)) |
                            (status_reg[1] ? XLEN'(1) : XLEN'(0));
            // Tag comparison handles redirects. Only overlapping stores can
            // change the buffered word; an eight-byte store covers two words.
            if (q_invalidate ||
                (q_mem && q_memwrite &&
                 (FETCH_SELECTIVE == 0 ||
                  (cache_tag[XLEN - 1 : 3] == q_addr[XLEN - 1 : 3] &&
                   (q_size == 3 || cache_tag[2] == q_addr[2])))) ||
                (FETCH_SELECTIVE == 0 && q_nextpc != pc + XLEN'(ilen)))
              cache_valid <= 0;
            pc <= q_nextpc;
            if (PERF != 0)
              instret <= instret + 64'd1;
            event_trace(1, 0, 0, q_nextpc, 0);
            if (q_stop)
              state <= STOP;
            else if (q_wait)
              state <= SLEEP;
            else
              state <= START;
          end
        end
        SLEEP:
          if (interrupt_ready)
            trap_entry(interrupt_cause, pc, 0, 0, 1);
          else if (pending != 0)
            state <= START;
        STOP: begin
        end
        default: begin
          fault_o <= 1;
          state <= STOP;
        end
      endcase
      regs[0] <= 0;
    end
  end
`ifdef MICA_ASSERTIONS
  assert property (@(posedge clk_i) disable iff(!rst_ni) regs[0] == '0);
  assert property (@(posedge clk_i) disable iff(!rst_ni) i_req_valid &&
                   !i_req_ready |=> i_req_valid && $stable(i_req_addr));
  assert property (
      @(posedge clk_i) disable iff(!rst_ni) d_req_valid &&
      !d_req_ready |=> d_req_valid &&
      $stable({d_req_addr, d_req_write, d_req_size, d_req_wdata, d_req_wstrb}));
  assert property (@(posedge clk_i) disable iff(!rst_ni) trace_valid &&
                       trace_trap && trace_cause == XLEN'(2) |->
                   !trace_retired);
  assert property (@(posedge clk_i) disable iff(!rst_ni) q_w1 && q_w2 |->
                   q_dst1 != q_dst2);
`endif
endmodule
