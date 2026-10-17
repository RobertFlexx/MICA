// MICA on Digilent Arty A7. Demo top for a small distributed-memory image.
// Confirm timing, resource utilization and pin constraints before using hardware.
// No external wiring is required beyond the board's onboard USB/JTAG/UART.
// SPDX-License-Identifier: MIT
module mica_arty_a7 #(
    parameter integer XLEN=32,
    parameter integer FLOW=1,
    parameter integer RAM_BYTES=4096,
    parameter INIT_FILE="program.mem8"
)(
    input logic CLK100MHZ,
    input logic btn_reset,
    output logic [3:0] led,
    output logic uart_txd
);
    logic [1:0] rst_release;
    logic rst_ni;
    logic [7:0] gpio;
    logic halted,fault;
    always_ff @(posedge CLK100MHZ or posedge btn_reset) begin
        if(btn_reset)rst_release<=2'b00;
        else rst_release<={rst_release[0],1'b1};
    end
    assign rst_ni=rst_release[1];
    mica_soc #(.XLEN(XLEN),.FLOW(FLOW),.RAM_BYTES(RAM_BYTES),
      .CLOCK_HZ(100000000),.BAUD(115200),.INIT_FILE(INIT_FILE)) soc (
       .clk_i(CLK100MHZ),.rst_ni(rst_ni),
       .uart_tx_o(uart_txd),.leds_o(gpio),
       .halted_o(halted),.fault_o(fault)
    );
    assign led={fault,halted,gpio[1:0]};
endmodule
