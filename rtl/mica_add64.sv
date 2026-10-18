// Equivalent add/sub experiments. Combinational operand isolation, no gated clocks.
// SPDX-License-Identifier: MIT
module mica_add64_full (
  input logic enable_i, narrow_i, sub_i,
  input logic [63:0] a_i,b_i,
  output logic [63:0] result_o
);
  wire [63:0] a=enable_i ? a_i:64'b0;
  wire [63:0] b=enable_i ? b_i:64'b0;
  wire [63:0] sum=a+(b ^ {64{sub_i}})+64'(sub_i);
  assign result_o=narrow_i ? {{32{sum[31]}},sum[31:0]}:sum;
endmodule

module mica_add64_segmented (
  input logic enable_i, narrow_i, sub_i,
  input logic [63:0] a_i,b_i,
  output logic [63:0] result_o
);
  wire upper_enable=enable_i && !narrow_i;
  wire [31:0] low_a=enable_i ? a_i[31:0]:32'b0;
  wire [31:0] low_b=(enable_i ? b_i[31:0]:32'b0) ^ {32{sub_i}};
  wire [32:0] low_sum={1'b0,low_a}+{1'b0,low_b}+33'(sub_i);
  // Both inputs and the carry are isolated during a narrow operation.
  wire [31:0] high_a=upper_enable ? a_i[63:32]:32'b0;
  wire [31:0] high_b=upper_enable ? (b_i[63:32] ^ {32{sub_i}}):32'b0;
  wire [31:0] high_sum=high_a+high_b+32'(upper_enable && low_sum[32]);
  assign result_o=narrow_i ? {{32{low_sum[31]}},low_sum[31:0]}:
    enable_i ? {high_sum,low_sum[31:0]}:64'b0;
endmodule
