`timescale 1ns / 1ps
module tb_peripherals;
  parameter integer XLEN = 32;
  logic clk = 0, rst_n = 0, rx = 1, tx, halted, fault;
  logic [7 : 0] leds;
  string received = "";
  integer irqs = 0;
  always
    #5 clk = ~clk;
  mica_soc #(.XLEN(XLEN),
             .TRAP(1),
             .PERF(1),
             .UART_RX(1),
             .CRC_ENABLE(1),
             .CLOCK_HZ(1600000),
             .BAUD(100000),
             .INIT_FILE(XLEN == 32 ? "program_peripherals.mem32"
                                   : "program_peripherals.mem64"))
      dut(.clk_i(clk),
          .rst_ni(rst_n),
          .irq_i(1'b0),
          .uart_rx_i(rx),
          .uart_tx_o(tx),
          .leds_o(leds),
          .halted_o(halted),
          .fault_o(fault));
  task send
      (input [7 : 0] data);
    begin
      rx = 0;
      repeat (16) @(negedge clk)
        ;
      for (integer i = 0; i < 8; i = i + 1) begin
        rx = data[i];
        repeat (16) @(negedge clk)
          ;
      end
      rx = 1;
      repeat (16) @(negedge clk)
        ;
    end
  endtask
  initial begin
    repeat (4) @(negedge clk)
      ;
    rst_n = 1;
    // Queue bytes while the CPU is still computing CRC, then drain via IRQs.
    repeat (80) @(negedge clk)
      ;
    send("A");
    send("B");
    send("C");
  end
  initial
    forever begin
      logic [7 : 0] data;
      @(negedge tx);
      repeat (24) @(posedge clk)
        ;
      for (integer i = 0; i < 8; i = i + 1) begin
        data[i] = tx;
        repeat (16) @(posedge clk)
          ;
      end
      if (!tx)
        $fatal(1, "UART echo stop bit");
      received = {received, data};
    end
  always @(negedge clk)
    if (rst_n && dut.core.trace_valid && dut.core.trace_trap &&
        dut.core.trace_cause == ((XLEN'(1) << (XLEN - 1)) | XLEN'(1)))
      irqs = irqs + 1;
  initial begin
    $dumpfile(XLEN == 32 ? "peripherals32.vcd" : "peripherals64.vcd");
    $dumpvars(0, tb_peripherals);
    repeat (10000) begin
      @(negedge clk);
      if (halted) begin
        repeat (180) @(negedge clk)
          ;
        if (fault || dut.a0 !== XLEN'(42) || received != "ABC" || irqs != 3 ||
            dut.rx_overrun || dut.rx_framing)
          $fatal(1, "peripheral firmware PC=%h a0=%h echo=%s irqs=%d", dut.pc,
                 dut.a0, received, irqs);
        if (dut.checksum.engine.crc_o !== 32'hcbf43926 ||
            dut.checksum.engine.count_o != 9)
          $fatal(1, "VHDL CRC result/count");
        $display(
            "Peripheral SoC PASS XLEN=%0d: CRC-32, serial RX FIFO, three precise IRQs and serial echo",
            XLEN);
        $finish;
      end
    end
    $fatal(1, "peripheral firmware timeout PC=%h", dut.pc);
  end
endmodule
