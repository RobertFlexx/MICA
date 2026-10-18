`timescale 1ns / 1ps
module tb_watchdog_mmio;
  parameter integer XLEN = 32;
  logic clk = 0, rst_n = 0, tx, halted, fault;
  logic [7 : 0] leds;
  integer irqs = 0;
  logic slept = 0;
  always #5 clk = ~clk;
  mica_soc #(.XLEN(XLEN), .MICA2(1), .TRAP(1), .WATCHDOG_ENABLE(1),
      .INIT_FILE(XLEN == 32 ? "program_watchdog_mmio.mem32" : "program_watchdog_mmio.mem64"))
    dut(.clk_i(clk), .rst_ni(rst_n), .irq_i(1'b0), .uart_rx_i(1'b1),
        .uart_tx_o(tx), .leds_o(leds), .halted_o(halted), .fault_o(fault));
  initial begin
    repeat (4) @(negedge clk);
    rst_n = 1;
    repeat (3000) begin
      @(negedge clk);
      if (dut.core.state == dut.core.SLEEP)
        slept = 1;
      if (dut.core.trace_valid && dut.core.trace_trap &&
          dut.core.trace_cause == ((XLEN'(1) << (XLEN - 1)) | XLEN'(1)))
        irqs = irqs + 1;
      if (halted) begin
        if (fault || dut.a0 !== XLEN'(42) || dut.core.regs[3] !== XLEN'(1) ||
            irqs != 1 || !slept || dut.watchdog_expired || dut.watchdog_early ||
            dut.watchdog_count != 0 || dut.watchdog_control != 0)
          $fatal(1, "watchdog MMIO XLEN=%0d irqs=%0d slept=%0d a0=%h", XLEN, irqs, slept, dut.a0);
        $display("PASS watchdog MMIO XLEN=%0d: timeout, WFI wake, precise IRQ, clear and resume", XLEN);
        $finish;
      end
    end
    $fatal(1, "watchdog MMIO timeout PC=%h", dut.pc);
  end
endmodule
