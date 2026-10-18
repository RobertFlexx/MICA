`timescale 1ns/1ps
module tb_mica_uart_rx;
  reg clk=0,rst_n=0,rx=1;
  wire valid,error;
  wire [7:0] data;
  integer received=0,errors=0,i;
  reg [7:0] bytes [0:255];
  always #5 clk=~clk;
  mica_uart_rx #(.CLOCK_HZ(1600),.BAUD(100)) dut(clk,rst_n,rx,valid,data,error);
  always @(negedge clk) if(rst_n) begin
    if(valid) begin bytes[received]=data;received=received+1;end
    if(error) errors=errors+1;
  end
  task bit_time;
    input value;
    begin rx=value;repeat(16) @(negedge clk);end
  endtask
  task frame;
    input [7:0] value;
    input good_stop;
    integer bit_no;
    begin
      bit_time(0);
      for(bit_no=0;bit_no<8;bit_no=bit_no+1) bit_time(value[bit_no]);
      bit_time(good_stop);
    end
  endtask
  initial begin
    $dumpfile("mica_uart_rx.vcd");$dumpvars(0,tb_mica_uart_rx);
    repeat(4) @(negedge clk);rst_n=1;
    rx=0;repeat(3) @(negedge clk);rx=1;repeat(32) @(negedge clk);
    if(received || errors) $fatal(1,"UART false-start glitch");
    for(i=0;i<256;i=i+1) frame(i[7:0],1);
    repeat(32) @(negedge clk);
    if(received!=256 || errors) $fatal(1,"UART frame count");
    for(i=0;i<256;i=i+1) if(bytes[i]!==i[7:0]) $fatal(1,"UART byte=%d got=%d",i,bytes[i]);
    frame(8'h55,0);repeat(100) @(negedge clk);
    if(errors!=1 || received!=256) $fatal(1,"UART framing/break recovery");
    bit_time(1);bit_time(0);rst_n=0;rx=1;
    repeat(4) @(negedge clk);rst_n=1;repeat(20) @(negedge clk);
    if(valid || error) $fatal(1,"UART reset during frame");
    $display("mica_uart_rx PASS: all bytes, back-to-back frames, glitch, break, reset");$finish;
  end
endmodule
