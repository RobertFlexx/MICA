// Minimal FPGA SoC/physical wrapper. Unified 64-KiB RAM, byte-initialized.
// Asynchronous ROM/RAM reads: FPGA target must support these memory styles.
// UART mapping: TX=0xffff0000 (writes), STATUS=0xffff000c (reads busy bit),
// LEDs=0xffff0010 (writes). No interrupt controller/MPU/atomic coherency.
// SPDX-License-Identifier: MIT
module mica_soc
    #(parameter integer XLEN = 32,
      parameter integer RAM_BYTES = 65536,
      parameter integer FLOW = 0,
      parameter integer CLOCK_HZ = 12000000,
      parameter integer BAUD = 115200,
      parameter INIT_FILE = "program.mem8")
    (input logic clk_i,
     input logic rst_ni,
     output logic uart_tx_o,
     output logic [7 : 0] leds_o,
     output logic halted_o,
     output logic fault_o);
  localparam integer B = XLEN / 8;
  logic [7 : 0] ram[0 : RAM_BYTES - 1];
  logic [XLEN - 1 : 0] ia, da, dwd, drd, pc, a0;
  logic [15 : 0] ird;
  logic [B - 1 : 0] strobes;
  logic rd, we, uart_busy, uart_send;
  integer i;
  initial begin
    for (integer k = 0; k < RAM_BYTES; k = k + 1)
      ram[k] = 8'b0;
    $readmemh(INIT_FILE, ram);
  end
  always_comb begin
    ird = 0;
    if (ia < RAM_BYTES - 1)
      ird = {ram[ia + XLEN'(1)], ram[ia]};
    drd = 0;
    // XLEN64 aligns the 0xffff000c status word to an 8-byte bus beat.
    // Expose it at lane[7:4], alongside the debug PC at lane[3:0].
    if (da == XLEN'('hffff0008))
      drd = XLEN'(pc[31 : 0]) | (XLEN'(uart_busy) << 32);
    else if (da == XLEN'('hffff000c))
      drd = XLEN'(uart_busy);
    else if (da < RAM_BYTES - B + 1) begin
      for (integer k = 0; k < B; k = k + 1)
        drd[k * 8 +: 8] = ram[da + XLEN'(k)];
    end
  end
  assign uart_send = we && (da == XLEN'('hffff0000)) && !uart_busy;
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)
      leds_o <= 0;
    else if (we) begin
      if (da == XLEN'('hffff0010))
        leds_o <= dwd[7 : 0];
      else if (da < RAM_BYTES - B + 1) begin
        for (integer j = 0; j < B; j = j + 1)
          if (strobes[j])
            ram[da + XLEN'(j)] <= dwd[j * 8 +: 8];
      end
    end
  end
  mica_core #(.XLEN(XLEN),
              .RAM_BYTES(RAM_BYTES),
              .FLOW(FLOW))
      core(.clk_i(clk_i),
           .rst_ni(rst_ni),
           .imem_addr_o(ia),
           .imem_rdata_i(ird),
           .dmem_addr_o(da),
           .dmem_wdata_o(dwd),
           .dmem_wstrb_o(strobes),
           .dmem_re_o(rd),
           .dmem_we_o(we),
           .dmem_rdata_i(drd),
           .halt_o(halted_o),
           .fault_o(fault_o),
           .pc_o(pc),
           .debug_a0_o(a0));
  mica_uart_tx #(.CLOCK_HZ(CLOCK_HZ),
                 .BAUD(BAUD))
      uart(.clk_i(clk_i),
           .rst_ni(rst_ni),
           .send_i(uart_send),
           .data_i(dwd[7 : 0]),
           .busy_o(uart_busy),
           .uart_tx_o(uart_tx_o));
endmodule
