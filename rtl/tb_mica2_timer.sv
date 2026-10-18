// MICA 2.0 timer wake from WFI; STOP must remain terminal despite pending IRQ.
`timescale 1ns / 1ps
module tb_mica2_timer;
  parameter integer XLEN = 32;
  logic clk = 0, rst_n = 0, tx, halted, fault;
  logic [7 : 0] leds;
  integer sleeping_cycles = 0;
  logic saw_wfi = 0, saw_handler = 0;
  always
    #5 clk = ~clk;
  mica_soc #(.XLEN(XLEN),
             .MICA2(1),
             .TRAP(1),
             .RAM_BYTES(65536),
             .INIT_FILE(XLEN == 64 ? "program_mica2_timer.mem64"
                                   : "program_mica2_timer.mem32"))
      dut(.clk_i(clk),
          .rst_ni(rst_n),
          .irq_i(1'b0),
          .uart_rx_i(1'b1),
          .uart_tx_o(tx),
          .leds_o(leds),
          .halted_o(halted),
          .fault_o(fault));
  initial begin
    repeat (4) @(negedge clk)
      ;
    rst_n = 1;
    repeat (20000) begin
      @(negedge clk);
      if (dut.core.trace_valid && dut.core.trace_retired &&
          dut.core.trace_insn == 32'h480)
        saw_wfi = 1;
      if (saw_wfi && !saw_handler && !dut.core.trace_valid) begin
        if (dut.core.i_req_valid || dut.core.d_req_valid)
          $fatal(1, "WFI issued a memory request before timer delivery");
        sleeping_cycles = sleeping_cycles + 1;
      end
      if (dut.core.trace_valid && dut.core.trace_trap) begin
        if (dut.core.trace_cause !== ((XLEN'(1) << (XLEN - 1)) | XLEN'(2)))
          $fatal(1, "unexpected timer trap cause %h", dut.core.trace_cause);
        saw_handler = 1;
      end
      if (halted) begin
        if (fault || !saw_wfi || !saw_handler || sleeping_cycles < 20 ||
            dut.a0 !== XLEN'(42))
          $fatal(1, "timer wake/return failed: sleep=%0d a0=%h",
                 sleeping_cycles, dut.a0);
        repeat (20) begin
          @(negedge clk);
          if (!halted || dut.core.i_req_valid || dut.core.d_req_valid ||
              dut.core.trace_valid)
            $fatal(1, "STOP resumed or retired an instruction");
        end
        $display("MICA2 timer WFI/STOP PASS XLEN=%0d sleeping_cycles=%0d", XLEN,
                 sleeping_cycles);
        $finish;
      end
    end
    $fatal(1, "timer wake timeout");
  end
endmodule
