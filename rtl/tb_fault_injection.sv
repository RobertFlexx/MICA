`timescale 1ns / 1ps
module tb_fault_injection;
  parameter integer REG_PARITY = 0;
  logic clk = 0, rst_n = 0, irq = 0, tx, halted, fault;
  logic [7 : 0] leds;
  integer kind, bit_index;
  logic injected = 0;
  always
    #5 clk = ~clk;
  mica_soc #(.MICA2(1),
             .TRAP(1),
             .REG_PARITY(REG_PARITY),
             .INIT_FILE("fault-probe.mem32"))
      dut(.clk_i(clk),
          .rst_ni(rst_n),
          .irq_i(irq),
          .uart_rx_i(1'b1),
          .uart_tx_o(tx),
          .leds_o(leds),
          .halted_o(halted),
          .fault_o(fault));
  initial begin
    if (!$value$plusargs("KIND=%d", kind))
      kind = 0;
    if (!$value$plusargs("BIT=%d", bit_index))
      bit_index = 0;
    repeat (3) @(negedge clk)
      ;
    rst_n = 1;
    wait(dut.core.state == dut.core.SLEEP);
    @(negedge clk);
    case (kind)
      0:
        dut.core.regs[1] = dut.core.regs[1] ^ (32'd1 << bit_index);
      1:
        dut.ram.mem[1024] = dut.ram.mem[1024] ^ (32'd1 << bit_index);
      2: begin
        // SLEEP=9, flipping bit 2 produces the unassigned state 13.
        $deposit(dut.core.state, 4'hd);
      end
      3:
        dut.core.pc[0] = 1'b1;
      default: begin
      end
    endcase
    injected = 1;
    irq = 1;
    if (kind == 4) begin
      // Inject a fabric-reported instruction error, not an arbitrary opcode.
      wait(dut.core.state == dut.core.IWAIT && dut.sv);
      force dut.se = 1'b1;
      @(posedge clk);
      #1;
      release dut.se;
    end
  end
  initial begin
    repeat (3000) begin
      @(negedge clk);
      if (injected && halted) begin
        if (kind == 2 || (kind == 0 && REG_PARITY != 0)) begin
          if (!fault || leds != 0)
            $fatal(1, "integrity fault did not fail-stop before GPIO");
          $display("PASS detected fail-stop kind=%0d bit=%0d parity=%0d", kind,
                   bit_index, REG_PARITY);
        end else if (kind == 3 || kind == 4) begin
          if (fault || leds != 0 ||
              dut.core.regs[4] !== (kind == 3 ? 32'd0 : 32'd1))
            $fatal(1, "precise fault delivery failed kind=%0d cause=%h", kind,
                   dut.core.regs[4]);
          $display("PASS detected precise trap kind=%0d", kind);
        end else begin
          if (fault || dut.a0 !== (32'd42 ^ (32'd1 << bit_index)))
            $fatal(1, "unprotected corruption result changed");
          $display(
              "PASS expected undetected corruption kind=%0d bit=%0d parity=%0d",
              kind, bit_index, REG_PARITY);
        end
        $finish;
      end
    end
    $fatal(1, "fault campaign timeout kind=%0d PC=%h", kind, dut.pc);
  end
endmodule
