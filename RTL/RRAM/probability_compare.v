module probability_compare #(
    parameter WIDTH = 8
)
(
    input  wire [WIDTH-1:0] rand_in,
    input  wire [WIDTH-1:0] threshold,

    output wire compare_result
);

    //----------------------------------------------------------------------
    // Probability Comparison Logic
    //----------------------------------------------------------------------
    assign compare_result = (rand_in < threshold);

endmodule