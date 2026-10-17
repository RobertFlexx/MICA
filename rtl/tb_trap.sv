// T: software ecall/eret or software-pending interrupt.
// Requires firmware assembled from examples/trap32 or trap_irq32.
`timescale 1ns / 1ps
module tb_trap;
  parameter integer IRQCASE = 0;
  logic clk = 0, rst_n = 0, uart_tx, halted, fault;
  logic [7 : 0] leds;
  always
    #5 clk = ~clk;
  mica_soc #(.TRAP(1),
             .RAM_BYTES(65536),
             .INIT_FILE("program_trap.mem8"))
      dut(.clk_i(clk),
          .rst_ni(rst_n),
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
          $fatal(1, "TRAP RTL fault PC=%h", dut.pc);
        if (IRQCASE != 0) begin
          if (dut.core.regs[3] !== 32'd12)
            $fatal(1, "interrupt resume state");
          if (dut.core.regs[4] !== 32'd42)
            $fatal(1, "handler not run");
          if (dut.core.regs[5] !== 32'h80000001)
            $fatal(1, "interrupt cause");
        end else begin
          if (dut.core.regs[3] !== 32'd18)
            $fatal(1, "ecall resume state");
          if (dut.core.regs[4] !== 32'd11)
            $fatal(1, "ecall cause");
        end
        $display("MICA-T smoke PASS IRQCASE=%0d", IRQCASE);
        $finish;
      end
    end
    $fatal(1, "MICA-T RTL timeout");
  end
endmodule
