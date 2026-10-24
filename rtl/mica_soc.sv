// MICA transactional on-chip SoC. Single clk_i domain. SPDX-License-Identifier: MIT
module mica_soc
    #(parameter integer XLEN = 32, RAM_BYTES = 65536, FLOW = 0, BITOPS = 0,
                        TRAP = 0, PERF = 0, REG_PARITY = 0,
      parameter integer XREG = 0, MUL = 0, MICA2 = 0, CLOCK_HZ = 12000000,
                        BAUD = 115200,
      parameter integer UART_RX = 0, CRC_ENABLE = 0, WATCHDOG_ENABLE = 0,
      parameter INIT_FILE = "program.mem32")
    (input logic clk_i, rst_ni, irq_i, uart_rx_i,
     output logic uart_tx_o,
     output logic [7 : 0] leds_o,
     output logic halted_o, fault_o);
  logic iv, ir, sv, sr, se, dv, dr, ds, dsr, dse, dw;
  logic [XLEN - 1 : 0] ia, da, wd, rd, pc, a0;
  logic [31 : 0] insn;
  logic [2 : 0] size;
  logic [XLEN / 8 - 1 : 0] strb;
  logic ram_ready, ram_valid, ram_error, mmio_valid, mmio_error;
  logic [XLEN - 1 : 0] ram_data, mmio_data;
  logic uart_busy, uart_send;
  logic [7 : 0] uart_byte, rx_byte, rx_front;
  logic rx_valid, rx_error, rx_ready, rx_available, rx_pop, rx_overrun,
        rx_framing, rx_irq_enable;
  logic [4 : 0] rx_level;
  logic crc_ready, crc_valid, crc_error, crc_clear, crc_push, crc_byte_ready,
        crc_busy;
  logic [7 : 0] crc_byte;
  logic [31 : 0] crc_data, crc_result, crc_count;
  logic [2 : 0] crc_lane;
  logic [1 : 0] watchdog_control;
  logic [31 : 0] watchdog_min, watchdog_max, watchdog_count;
  logic watchdog_expired, watchdog_early;
  logic [63 : 0] cycles;
  (* ASYNC_REG = "TRUE" *) logic [1 : 0] irq_sync;
  wire ram_select = da < XLEN'(RAM_BYTES);
  wire crc_select =
           CRC_ENABLE != 0 && da >= XLEN'('hffff0040) && da < XLEN'('hffff0050);
  wire uart_select = da == XLEN'('hffff0000) && dw && size <= 2;
  wire mmio_ready = (!mmio_valid || dsr) && (!uart_select || !uart_busy);
  wire mmio_accept = dv && !ram_select && !crc_select && mmio_ready;
  wire [XLEN - 1 : 0] unshifted = wd >> (8 * int'(da & XLEN'(XLEN / 8 - 1)));
  wire [31 : 0] word_write = unshifted[31 : 0] & (size == 0   ? 32'hff
                                                  : size == 1 ? 32'hffff
                                                              : 32'hffffffff);
  wire [31 : 0] rx_status = {
                    19'b0,      rx_level,   4'b0,        1'(UART_RX != 0),
                    rx_overrun, rx_framing, rx_available};
  wire unused_debug = ^{
    pc, a0, unshifted, rx_byte, crc_clear, crc_push, crc_byte, crc_byte_ready,
        crc_busy, crc_result, crc_count
  };
  assign dr = ram_select ? ram_ready : crc_select ? crc_ready : mmio_ready;
  assign ds = ram_valid || mmio_valid || crc_valid;
  assign rd = crc_valid    ? XLEN'(crc_data) << (8 * int'(crc_lane))
              : mmio_valid ? mmio_data
                           : ram_data;
  assign dse = crc_valid ? crc_error : mmio_valid ? mmio_error : ram_error;
  assign uart_send = mmio_accept && uart_select;
  assign uart_byte = unshifted[7 : 0];
  assign rx_pop = mmio_accept && !dw && size <= 2 && da == XLEN'('hffff0014);
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      irq_sync <= 0;
      cycles <= 0;
      leds_o <= 0;
      mmio_valid <= 0;
      mmio_data <= 0;
      mmio_error <= 0;
      rx_overrun <= 0;
      rx_framing <= 0;
      rx_irq_enable <= 0;
      crc_lane <= 0;
      watchdog_control <= 0;
      watchdog_min <= 0;
      watchdog_max <= '1;
    end else begin
      irq_sync <= {irq_sync[0], irq_i};
      cycles <= cycles + 64'd1;
      if (crc_select && dv && crc_ready)
        crc_lane <= 3'(da & XLEN'(XLEN / 8 - 1));
      if (dsr)
        mmio_valid <= 0;
      if (mmio_accept) begin
        mmio_valid <= 1;
        mmio_error <= 0;
        mmio_data <= 0;
        if (size > 2)
          mmio_error <= 1;
        else if (da == XLEN'('hffff0000) && dw) begin
        end else if (da == XLEN'('hffff0008) && !dw)
          mmio_data <= XLEN'(cycles[31 : 0])
                       << (8 * int'(da & XLEN'(XLEN / 8 - 1)));
        else if (da == XLEN'('hffff000c) && !dw)
          mmio_data <= XLEN'(uart_busy) << (8 * int'(da & XLEN'(XLEN / 8 - 1)));
        else if (da == XLEN'('hffff0010)) begin
          if (dw)
            leds_o <= unshifted[7 : 0];
          else
            mmio_data <= XLEN'(leds_o) << (8 * int'(da & XLEN'(XLEN / 8 - 1)));
        end else if (UART_RX != 0 && da == XLEN'('hffff0014) && !dw)
          mmio_data <= XLEN'(rx_front) << (8 * int'(da & XLEN'(XLEN / 8 - 1)));
        else if (UART_RX != 0 && da == XLEN'('hffff0018) && !dw)
          mmio_data <= XLEN'(rx_status);
        else if (UART_RX != 0 && da == XLEN'('hffff001c)) begin
          if (dw) begin
            rx_irq_enable <= unshifted[0];
            if (unshifted[1]) begin
              rx_overrun <= 0;
              rx_framing <= 0;
            end
          end else
            mmio_data <= XLEN'(rx_irq_enable)
                         << (8 * int'(da & XLEN'(XLEN / 8 - 1)));
        end else if (da == XLEN'('hffff0020) && !dw)
          mmio_data <=
              XLEN'((UART_RX != 0 ? 1 : 0) | (CRC_ENABLE != 0 ? 2 : 0) |
                    (WATCHDOG_ENABLE != 0 ? 4 : 0));
        else if (WATCHDOG_ENABLE != 0 && da == XLEN'('hffff0060)) begin
          if (dw)
            watchdog_control <= unshifted[1 : 0];
          else
            mmio_data <= XLEN'(watchdog_control);
        end else if (WATCHDOG_ENABLE != 0 && da == XLEN'('hffff0064)) begin
          if (dw)
            watchdog_min <= word_write;
          else
            mmio_data <= XLEN'(watchdog_min)
                         << (8 * int'(da & XLEN'(XLEN / 8 - 1)));
        end else if (WATCHDOG_ENABLE != 0 && da == XLEN'('hffff0068)) begin
          if (dw)
            watchdog_max <= word_write;
          else
            mmio_data <= XLEN'(watchdog_max);
        end else if (WATCHDOG_ENABLE != 0 && dw &&
                     (da == XLEN'('hffff006c) || da == XLEN'('hffff0078))) begin
        end else if (WATCHDOG_ENABLE != 0 && !dw && da == XLEN'('hffff0070))
          mmio_data <= XLEN'({watchdog_early, watchdog_expired});
        else if (WATCHDOG_ENABLE != 0 && !dw && da == XLEN'('hffff0074))
          mmio_data <= XLEN'(watchdog_count)
                       << (8 * int'(da & XLEN'(XLEN / 8 - 1)));
        else
          mmio_error <= 1;
      end
      // A new error wins over a simultaneous software clear.
      if (rx_error)
        rx_framing <= 1;
      if (rx_valid && !rx_ready)
        rx_overrun <= 1;
    end
  end
  mica_core_txn #(.XLEN(XLEN),
                  .XREG(XREG),
                  .MUL(MUL),
                  .FLOW(FLOW),
                  .BITOPS(BITOPS),
                  .TRAP(TRAP),
                  .PERF(PERF),
                  .MICA2(MICA2),
                  .REG_PARITY(REG_PARITY),
                  .RAM_BYTES(RAM_BYTES))
      core(.clk_i(clk_i),
           .rst_ni(rst_ni),
           .irq_i(
               irq_sync[1] || (rx_irq_enable && rx_available) ||
               (watchdog_control[1] && (watchdog_expired || watchdog_early))),
           .i_req_valid(iv),
           .i_req_ready(ir),
           .i_req_addr(ia),
           .i_rsp_valid(sv),
           .i_rsp_ready(sr),
           .i_rsp_rdata(insn),
           .i_rsp_error(se),
           .d_req_valid(dv),
           .d_req_ready(dr),
           .d_req_addr(da),
           .d_req_write(dw),
           .d_req_size(size),
           .d_req_wdata(wd),
           .d_req_wstrb(strb),
           .d_rsp_valid(ds),
           .d_rsp_ready(dsr),
           .d_rsp_rdata(rd),
           .d_rsp_error(dse),
           .halt_o(halted_o),
           .fault_o(fault_o),
           .pc_o(pc),
           .debug_a0_o(a0),
           .trace_valid(),
           .trace_retired(),
           .trace_trap(),
           .trace_order(),
           .trace_pc(),
           .trace_next_pc(),
           .trace_cause(),
           .trace_insn(),
           .trace_length(),
           .trace_regs(),
           .trace_mem_valid(),
           .trace_mem_write(),
           .trace_mem_addr(),
           .trace_mem_data(),
           .trace_mem_bytes());
  mica_sram_txn #(.DATA_W(XLEN),
                  .ADDR_W(XLEN),
                  .RAM_BYTES(RAM_BYTES),
                  .INIT_FILE(INIT_FILE))
      ram(.clk_i(clk_i),
          .rst_ni(rst_ni),
          .i_req_valid(iv),
          .i_req_ready(ir),
          .i_req_addr(ia),
          .i_rsp_valid(sv),
          .i_rsp_ready(sr),
          .i_rsp_rdata(insn),
          .i_rsp_error(se),
          .d_req_valid(dv && ram_select),
          .d_req_ready(ram_ready),
          .d_req_addr(da),
          .d_req_write(dw),
          .d_req_size(size),
          .d_req_wdata(wd),
          .d_req_wstrb(strb),
          .d_rsp_valid(ram_valid),
          .d_rsp_ready(dsr),
          .d_rsp_rdata(ram_data),
          .d_rsp_error(ram_error));
  mica_uart_tx #(.CLOCK_HZ(CLOCK_HZ),
                 .BAUD(BAUD))
      uart(.clk_i(clk_i),
           .rst_ni(rst_ni),
           .send_i(uart_send),
           .data_i(uart_byte),
           .busy_o(uart_busy),
           .uart_tx_o(uart_tx_o));
  generate
    if (WATCHDOG_ENABLE != 0) begin : safety
      wire watchdog_write = mmio_accept && dw && size <= 2;
      wire watchdog_kick = watchdog_write && da == XLEN'('hffff006c);
      wire watchdog_clear =
               watchdog_write && da == XLEN'('hffff0078) && unshifted[0];
      // GHDL converts the VHDL counter and watchdog for mixed-language builds.
      mica_watchdog watchdog(.clk_i(clk_i),
                             .rst_ni(rst_ni),
                             .enable_i(watchdog_control[0]),
                             .kick_i(watchdog_kick),
                             .clear_i(watchdog_clear),
                             .min_ticks_i(watchdog_min),
                             .max_ticks_i(watchdog_max),
                             .expired_o(watchdog_expired),
                             .early_o(watchdog_early),
                             .count_o(watchdog_count));
    end else begin : no_safety
      assign watchdog_expired = 0;
      assign watchdog_early = 0;
      assign watchdog_count = 0;
    end
    if (UART_RX != 0) begin : receive
      mica_uart_rx #(.CLOCK_HZ(CLOCK_HZ),
                     .BAUD(BAUD))
          rx(.clk_i(clk_i),
             .rst_ni(rst_ni),
             .uart_rx_i(uart_rx_i),
             .byte_valid_o(rx_valid),
             .byte_o(rx_byte),
             .framing_error_o(rx_error));
      mica_sync_fifo #(.WIDTH(8),
                       .DEPTH(16))
          fifo(.clk_i(clk_i),
               .rst_ni(rst_ni),
               .push_valid_i(rx_valid),
               .push_ready_o(rx_ready),
               .push_data_i(rx_byte),
               .pop_valid_o(rx_available),
               .pop_ready_i(rx_pop),
               .pop_data_o(rx_front),
               .level_o(rx_level));
    end else begin : no_receive
      assign rx_valid = 0;
      assign rx_byte = 0;
      assign rx_error = 0;
      assign rx_ready = 0;
      assign rx_available = 0;
      assign rx_front = 0;
      assign rx_level = 0;
      wire unused_rx = uart_rx_i;
    end
  endgenerate
  generate
    if (CRC_ENABLE != 0) begin : checksum
      mica_crc_mmio bridge(.clk_i(clk_i),
                           .rst_ni(rst_ni),
                           .req_valid(dv && crc_select),
                           .req_ready(crc_ready),
                           .req_addr(da[3 : 0]),
                           .req_write(dw),
                           .req_size(size),
                           .req_wdata(unshifted[31 : 0]),
                           .rsp_valid(crc_valid),
                           .rsp_ready(dsr),
                           .rsp_rdata(crc_data),
                           .rsp_error(crc_error),
                           .clear_o(crc_clear),
                           .byte_valid_o(crc_push),
                           .byte_o(crc_byte),
                           .byte_ready_i(crc_byte_ready),
                           .busy_i(crc_busy),
                           .crc_i(crc_result),
                           .count_i(crc_count));
      mica_crc32 engine(.clk_i(clk_i),
                        .rst_ni(rst_ni),
                        .clear_i(crc_clear),
                        .byte_valid_i(crc_push),
                        .byte_ready_o(crc_byte_ready),
                        .byte_i(crc_byte),
                        .busy_o(crc_busy),
                        .crc_o(crc_result),
                        .count_o(crc_count));
    end else begin : no_checksum
      assign crc_ready = 0;
      assign crc_valid = 0;
      assign crc_error = 0;
      assign crc_data = 0;
      assign crc_clear = 0;
      assign crc_push = 0;
      assign crc_byte = 0;
      assign crc_byte_ready = 0;
      assign crc_busy = 0;
      assign crc_result = 0;
      assign crc_count = 0;
    end
  endgenerate
endmodule
