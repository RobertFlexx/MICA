// 8N1 UART receiver. Two-flop input synchronizer, midpoint sampling.
// DIVISOR must be >= 4. A bad stop bit emits one framing error and waits high.
// Byte/error outputs pulse for one clock; the consumer must buffer received data.
// SPDX-License-Identifier: MIT
module mica_uart_rx #(
  parameter CLOCK_HZ = 12000000, BAUD = 115200,
  parameter DIVISOR = CLOCK_HZ / BAUD,
  parameter COUNT_W = (DIVISOR > 1 ? $clog2(DIVISOR) : 1)
) (
  input wire clk_i, rst_ni, uart_rx_i,
  output reg byte_valid_o,
  output reg [7:0] byte_o,
  output reg framing_error_o
);
  localparam [2:0] IDLE=0, START=1, DATA=2, STOP=3, WAIT_HIGH=4;
  localparam integer FULL_TICKS = DIVISOR-1, HALF_TICKS = (DIVISOR-1)/2;
  localparam [COUNT_W-1:0] BIT_TICKS = FULL_TICKS[COUNT_W-1:0], START_TICKS = HALF_TICKS[COUNT_W-1:0];
  (* ASYNC_REG = "TRUE" *) reg [1:0] rx_sync;
  reg [2:0] state, bit_index;
  reg [COUNT_W-1:0] ticks;
  reg [7:0] shift;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rx_sync <= 2'b11;
      state <= IDLE;
      ticks <= 0;
      bit_index <= 0;
      shift <= 0;
      byte_valid_o <= 0;
      byte_o <= 0;
      framing_error_o <= 0;
    end else begin
      rx_sync <= {rx_sync[0],uart_rx_i};
      byte_valid_o <= 0;
      framing_error_o <= 0;
      case (state)
        IDLE: if (!rx_sync[1]) begin
          ticks <= START_TICKS;
          state <= START;
        end
        START: if (ticks != 0) ticks <= ticks - 1'b1;
          else if (rx_sync[1]) state <= IDLE; // Reject a short low glitch.
          else begin
            ticks <= BIT_TICKS;
            bit_index <= 0;
            state <= DATA;
          end
        DATA: if (ticks != 0) ticks <= ticks - 1'b1;
          else begin
            shift[bit_index] <= rx_sync[1];
            ticks <= BIT_TICKS;
            if (bit_index == 7) state <= STOP;
            else bit_index <= bit_index + 1'b1;
          end
        STOP: if (ticks != 0) ticks <= ticks - 1'b1;
          else if (rx_sync[1]) begin
            byte_o <= shift;
            byte_valid_o <= 1;
            state <= IDLE;
          end else begin
            framing_error_o <= 1;
            state <= WAIT_HIGH;
          end
        WAIT_HIGH: if (rx_sync[1]) state <= IDLE;
        default: state <= IDLE;
      endcase
    end
  end
endmodule
