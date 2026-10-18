module add64_formal
    (input [63 : 0] a, b,
     input narrow, sub, enable);
  wire [63 : 0] full_result, segmented_result;
  mica_add64_full full(enable,
                       narrow,
                       sub,
                       a,
                       b,
                       full_result);
  mica_add64_segmented segmented(enable,
                                 narrow,
                                 sub,
                                 a,
                                 b,
                                 segmented_result);
  always @*
    assert (full_result == segmented_result);
endmodule
