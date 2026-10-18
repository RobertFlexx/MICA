`timescale 1ns/1ps
module tb_firmware;
  parameter integer SCHEDULER=0;
  logic clk=0,rst_n=0,tx,halted,fault;
  logic [7:0] leds;
  integer chars=0;
  string received="";
  always #5 clk=~clk;
  mica_soc #(.TRAP(1),.PERF(1),.CLOCK_HZ(1000000),.BAUD(100000),
    .INIT_FILE("program_firmware.mem32")) dut (
    .clk_i(clk),.rst_ni(rst_n),.uart_rx_i(1'b1),.irq_i(1'b0),.uart_tx_o(tx),.leds_o(leds),
    .halted_o(halted),.fault_o(fault));
  // Sample the actual 8N1 pin at bit centers (ten CPU clocks per bit).
  initial forever begin
    logic [7:0] byte_value;
    @(negedge tx);
    repeat(15) @(posedge clk);
    for(integer j=0;j<8;j=j+1) begin
      byte_value[j]=tx;
      repeat(10) @(posedge clk);
    end
    if(!tx) $fatal(1,"UART stop bit missing");
    received={received,byte_value};chars=chars+1;
  end
  initial begin
    $dumpfile("firmware.vcd");$dumpvars(0,tb_firmware);
    repeat(4) @(negedge clk);
    rst_n=1;
    repeat(400000) begin
      @(negedge clk);
      if(halted) begin
        if(fault || dut.a0!==32'd42) $fatal(1,"firmware failure PC=%h x1=%h",dut.pc,dut.a0);
        if(SCHEDULER==0) begin
          repeat(120) @(negedge clk);
          if(received!="MICA 1.0 OK\n" || leds!==8'd3) $fatal(1,"UART/GPIO mismatch: %s",received);
        end
        $display("MICA firmware PASS scheduler=%0d UART=%s",SCHEDULER,received);
        $finish;
      end
    end
    $fatal(1,"firmware timeout");
  end
endmodule
