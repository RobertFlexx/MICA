// Single-clock ready/valid FIFO. No reset on payload storage.
// A full FIFO accepts a push on the same edge as a pop. DEPTH need not be 2**N.
// SPDX-License-Identifier: MIT
module mica_sync_fifo
    #(parameter WIDTH = 8, DEPTH = 16,
      parameter COUNT_W = (DEPTH > 0 ? $clog2(DEPTH + 1) : 1),
                PTR_W = (DEPTH > 1 ? $clog2(DEPTH) : 1))
    (input wire clk_i, rst_ni,
     input wire push_valid_i,
     output wire push_ready_o,
     input wire [WIDTH - 1 : 0] push_data_i,
     output wire pop_valid_o,
     input wire pop_ready_i,
     output wire [WIDTH - 1 : 0] pop_data_o,
     output wire [COUNT_W - 1 : 0] level_o);
  localparam [COUNT_W - 1 : 0] CAPACITY = DEPTH[COUNT_W - 1 : 0];
  localparam integer LAST_INDEX = DEPTH - 1;
  localparam [PTR_W - 1 : 0] LAST = LAST_INDEX[PTR_W - 1 : 0];
  reg [WIDTH - 1 : 0] storage[0 : DEPTH - 1];
  reg [PTR_W - 1 : 0] head, tail;
  reg [COUNT_W - 1 : 0] count;
  initial begin
    if (WIDTH < 1 || DEPTH < 1 || COUNT_W < $clog2(DEPTH + 1) || PTR_W < 1 ||
        PTR_W < $clog2(DEPTH))
      $fatal(1, "invalid FIFO parameters");
  end
  wire pop = pop_valid_o && pop_ready_i;
  wire push = push_valid_i && push_ready_o;
  assign pop_valid_o = rst_ni && (count != 0);
  assign push_ready_o = rst_ni && ((count < CAPACITY) || pop);
  assign pop_data_o = pop_valid_o ? storage[head] : {WIDTH{1'b0}};
  assign level_o = count;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      head <= 0;
      tail <= 0;
      count <= 0;
    end else begin
      if (push) begin
        storage[tail] <= push_data_i;
        tail <= tail == LAST ? {PTR_W{1'b0}} : tail + 1'b1;
      end
      if (pop)
        head <= head == LAST ? {PTR_W{1'b0}} : head + 1'b1;
      case ({push, pop})
        2'b10:
          count <= count + 1'b1;
        2'b01:
          count <= count - 1'b1;
        default: begin
        end
      endcase
    end
  end
endmodule
