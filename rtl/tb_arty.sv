`timescale 1ns/1ps
// Actual board top, 100 MHz input, 4 KiB image and integer UART divider.
module tb_arty;
  localparam integer DIVISOR=100000000/115200;
  logic clk=0,button=1,tx;
  logic [3:0] leds;
  string received="";
  always #5 clk=~clk;
  mica_arty_a7 #(.CRC_ENABLE(1),.INIT_FILE("program_arty.mem32")) dut (
    .CLK100MHZ(clk),.btn_reset(button),.uart_rxd(1'b1),.uart_txd(tx),.led(leds));
  initial begin
    repeat(4) @(negedge clk);button=0;
    @(negedge clk);if(dut.rst_ni!==0) $fatal(1,"reset released before two clock edges");
    @(negedge clk);if(dut.rst_ni!==1) $fatal(1,"synchronized reset release");
  end
  initial forever begin
    logic [7:0] data;
    @(negedge tx);repeat(DIVISOR+DIVISOR/2) @(posedge clk);
    for(integer i=0;i<8;i=i+1) begin data[i]=tx;repeat(DIVISOR) @(posedge clk);end
    if(!tx) $fatal(1,"board UART stop bit");
    received={received,data};
  end
  initial begin
    $dumpfile("arty.vcd");$dumpvars(1,tb_arty);
    repeat(200000) begin
      @(negedge clk);
      if(leds[3]) $fatal(1,"Arty top fault");
      if(leds[2]) begin
        repeat(12*DIVISOR) @(negedge clk);
        if(leds!==4'b0111 || received!="MICA 1.0 OK\n" || dut.soc.a0!==32'd42)
          $fatal(1,"Arty top LEDs=%h UART=%s",leds,received);
        $display("Arty A7 top simulation PASS: 100 MHz, 4 KiB, reset release, timer IRQ, GPIO and 115200 UART");$finish;
      end
    end
    $fatal(1,"Arty top simulation timeout");
  end
endmodule
