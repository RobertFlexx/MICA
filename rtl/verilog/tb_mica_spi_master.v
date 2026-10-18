`timescale 1ns/1ps
module tb_mica_spi_master;
  parameter CLOCK_DIV = 2;
  reg clk = 0, rst_n = 0;
  wire [3:0] done;
  always #5 clk = ~clk;
  genvar mode;
  generate for (mode=0; mode<4; mode=mode+1) begin: modes
    reg valid = 0, ready = 0;
    reg [7:0] data = 0;
    wire accept, response, sclk, mosi, cs_n;
    reg miso = 0;
    reg [7:0] expected_rx = 0, captured = 0;
    wire [7:0] result;
    reg complete = 0;
    integer byte_value, hold_cycle, edges, samples;
    time last_edge;
    assign done[mode] = complete;
    mica_spi_master #(.CLOCK_DIV(CLOCK_DIV), .CPOL(mode/2), .CPHA(mode%2)) dut (
      .clk_i(clk), .rst_ni(rst_n), .req_valid_i(valid), .req_ready_o(accept),
      .req_data_i(data), .rsp_valid_o(response), .rsp_ready_i(ready), .rsp_data_o(result),
      .sclk_o(sclk), .mosi_o(mosi), .miso_i(miso), .cs_no(cs_n));
    always @(negedge cs_n) begin
      edges = 0; samples = 0; captured = 0; miso = expected_rx[7]; last_edge = $time;
    end
    always @(sclk) if (!cs_n && rst_n) begin
      if ($time - last_edge != CLOCK_DIV * 10) $fatal(1,"SPI clock divider");
      last_edge = $time;
      edges = edges + 1;
      if (sclk == (mode/2 == mode%2)) begin
        captured = {captured[6:0],mosi}; samples = samples + 1;
      end else if (samples < 8) miso = expected_rx[7-samples];
    end
    always @(negedge rst_n) begin
      #1;
      if (!cs_n || response || sclk !== (mode/2 != 0)) $fatal(1,"SPI reset");
    end
    initial begin
      edges = 0;
      wait (rst_n); @(negedge clk);
      for (byte_value=0; byte_value<256; byte_value=byte_value+1) begin
        if (!accept || !cs_n || sclk !== (mode/2 != 0)) $fatal(1,"SPI idle");
        data = byte_value[7:0]; expected_rx = 8'ha5 ^ byte_value[7:0]; valid = 1;
        @(negedge clk); valid = 0; data = 0;
        while (!response) begin
          if (accept) $fatal(1,"SPI accepted competing request");
          @(negedge clk);
        end
        if (result !== expected_rx || captured !== byte_value[7:0] ||
            samples != 8 || edges != 16 || !cs_n || sclk !== (mode/2 != 0))
          $fatal(1,"SPI mode %0d byte %0d returned %0h",mode,byte_value,result);
        for (hold_cycle=0; hold_cycle<3; hold_cycle=hold_cycle+1) begin
          @(negedge clk);
          if (!response || accept || result !== expected_rx || !cs_n)
            $fatal(1,"SPI response backpressure");
        end
        ready = 1; @(negedge clk); ready = 0;
      end
      valid = 1; @(negedge clk); valid = 0; complete = 1;
    end
  end endgenerate
  initial begin
    repeat (3) @(negedge clk); rst_n = 1;
    wait (&done); repeat (3) @(negedge clk); rst_n = 0; #2;
    $display("SPI PASS: four modes, 256 bytes/mode, independent slave, held responses, reset"); $finish;
  end
  initial begin #500000; $fatal(1,"SPI timeout"); end
endmodule
