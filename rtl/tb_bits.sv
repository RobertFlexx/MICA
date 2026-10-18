// Bit datapath smoke test with preassembled MICA32 or MICA64 firmware.
// Run with make sim-bits32 or make sim-bits64. No board is needed.
`timescale 1ns / 1ps
module tb_bits;
  parameter integer XLEN = 32;
  logic clk = 0, rst_n = 0, uart_tx, halted, fault;
  logic [7 : 0] leds;
  always
    #5 clk = ~clk;
  mica_soc #(.XLEN(XLEN),
             .BITOPS(1),
             .RAM_BYTES(65536),
             .INIT_FILE(XLEN == 64 ? "program_bits.mem64"
                                   : "program_bits.mem32"))
      dut(.clk_i(clk),
          .rst_ni(rst_n),
          .uart_rx_i(1'b1),
          .irq_i(1'b0),
          .uart_tx_o(uart_tx),
          .leds_o(leds),
          .halted_o(halted),
          .fault_o(fault));
  initial begin
    repeat (4) @(negedge clk)
      ;
    rst_n = 1;
    repeat (1000) begin
      @(negedge clk);
      if (halted) begin
        if (fault)
          $fatal(1, "BIT RTL fault PC=%h", dut.pc);
        if (dut.a0 !== XLEN'(32))
          $fatal(1, "BIT feature CSR mismatch: %h", dut.a0);
        if (XLEN == 32) begin
          if (dut.core.regs[3] !== XLEN'(0))
            $fatal(1, "clz32");
          if (dut.core.regs[4] !== XLEN'(0))
            $fatal(1, "ctz32");
          if (dut.core.regs[5] !== XLEN'(8))
            $fatal(1, "popcount32");
          if (dut.core.regs[6] !== XLEN'(32'hff000000))
            $fatal(1, "ror32");
        end else begin
          if (dut.core.regs[3] !== XLEN'(64'hefcdab8967452301))
            $fatal(1, "rev8");
          if (dut.core.regs[4] !== XLEN'(64'hef0123456789abcd))
            $fatal(1, "ror64");
          if (dut.core.regs[5] !== XLEN'(32))
            $fatal(1, "popcount64");
          if (dut.core.regs[6] !== XLEN'(7))
            $fatal(1, "clz64");
        end
        $display("MICA BIT RTL smoke PASS XLEN=%0d", XLEN);
        $finish;
      end
    end
    $fatal(1, "BIT RTL timeout");
  end
endmodule
