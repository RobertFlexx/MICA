`timescale 1ns / 1ps
module tb_sensor_node;
  parameter integer COUNTER_ADDR = 0;
  logic clk = 0, rst_n = 0, tx, halted, fault;
  logic [7 : 0] leds;
  logic [7 : 0] expected[0 : 15];
  integer received = 0, interrupts = 0, cycles = 0, sleep_cycles = 0;
  integer pending_cycle = 0, maximum_entry = 0;
  wire sleeping = dut.core.state == dut.core.SLEEP;
  always
    #5 clk = ~clk;
  mica_soc #(.XLEN(32),
             .MICA2(1),
             .XREG(1),
             .MUL(1),
             .FLOW(1),
             .BITOPS(1),
             .TRAP(1),
             .PERF(1),
             .REG_PARITY(1),
             .WATCHDOG_ENABLE(1),
             .CLOCK_HZ(1600000),
             .BAUD(100000),
             .INIT_FILE("sensor-node.mem32"))
      dut(.clk_i(clk),
          .rst_ni(rst_n),
          .irq_i(1'b0),
          .uart_rx_i(1'b1),
          .uart_tx_o(tx),
          .leds_o(leds),
          .halted_o(halted),
          .fault_o(fault));
  initial
    forever begin
      logic [7 : 0] byte_value;
      @(negedge tx);
      repeat (24) @(posedge clk)
        ;
      for (integer bit_index = 0; bit_index < 8; bit_index = bit_index + 1)
      begin
        byte_value[bit_index] = tx;
        repeat (16) @(posedge clk)
          ;
      end
      if (!tx || received >= 16 || byte_value !== expected[received])
        $fatal(1, "sensor UART byte %0d: %h", received, byte_value);
      received = received + 1;
    end
  always @(negedge clk)
    if (rst_n && !halted) begin
      cycles = cycles + 1;
      if (sleeping) begin
        sleep_cycles = sleep_cycles + 1;
        if (dut.iv || dut.dv ||
            (dut.core.trace_valid && dut.core.trace_insn != 32'h480))
          $fatal(1, "sensor issued work during sleep");
        if (dut.core.pending[1] && !pending_cycle)
          pending_cycle = cycles;
      end
      if (dut.core.trace_valid && dut.core.trace_trap &&
          dut.core.trace_cause == 32'h80000002) begin
        interrupts = interrupts + 1;
        if (!pending_cycle)
          $fatal(1, "timer interrupt did not wake sleep");
        if (cycles - pending_cycle > maximum_entry)
          maximum_entry = cycles - pending_cycle;
        pending_cycle = 0;
      end
    end
  initial begin
    integer metrics;
    $readmemh("expected.hex", expected);
    $dumpfile("sensor-node.vcd");
    $dumpvars(0, tb_sensor_node.sleeping, tb_sensor_node.clk, dut.core);
    repeat (4) @(negedge clk)
      ;
    rst_n = 1;
    repeat (200000) begin
      @(negedge clk);
      if (halted) begin
        $dumpoff;
        repeat (200) @(negedge clk)
          ;
        if (fault || dut.a0 !== 42 || interrupts != 4 || received != 16 ||
            dut.ram.mem[COUNTER_ADDR / 4] !== 4 || dut.watchdog_expired ||
            dut.watchdog_early || sleep_cycles < 7500 || maximum_entry != 1)
          $fatal(1, "sensor result a0=%h irq=%0d rx=%0d sleep=%0d latency=%0d",
                 dut.a0, interrupts, received, sleep_cycles, maximum_entry);
        metrics = $fopen("rtl-results.json", "w");
        $fdisplay(
            metrics,
            "{\"cycles\":%0d,\"sleep_cycles\":%0d,\"active_cycles\":%0d,\"timer_interrupts\":%0d,\"maximum_observed_entry_cycles\":%0d}",
            cycles, sleep_cycles, cycles - sleep_cycles, interrupts,
            maximum_entry);
        $fclose(metrics);
        $display(
            "PASS compiled sensor RTL: %0d cycles, %0d asleep, four verified packets, parity and watchdog enabled",
            cycles, sleep_cycles);
        $finish;
      end
    end
    $fatal(1, "compiled sensor timeout PC=%h", dut.pc);
  end
endmodule
