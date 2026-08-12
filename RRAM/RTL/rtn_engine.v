module rtn_engine #

(

    parameter WIDTH = 8

)

(

    input  wire                     transition_bit,

    input  wire [WIDTH-1:0]         rand_in,

    input  wire [WIDTH-1:0]         noise_threshold,

    output wire                     entropy_bit

);

    //----------------------------------------------------------------------
    // Internal Signal
    //----------------------------------------------------------------------

    wire flip_enable;

    //----------------------------------------------------------------------
    // Probability Comparator
    //----------------------------------------------------------------------

    probability_compare #

    (

        .WIDTH(WIDTH)

    )

    RTN_COMPARE

    (

        .rand_in(rand_in),

        .threshold(noise_threshold),

        .compare_result(flip_enable)

    );

    //----------------------------------------------------------------------
    // RTN Flip Logic
    //----------------------------------------------------------------------

    assign entropy_bit = transition_bit ^ flip_enable;

endmodule