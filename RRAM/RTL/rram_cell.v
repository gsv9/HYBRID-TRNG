`timescale 1ns / 1ps

module rram_cell #(

    parameter WIDTH = 8,

    parameter INIT_SET_THRESHOLD   = 8'd145,

    parameter INIT_RESET_THRESHOLD = 8'd110,

    parameter INIT_NOISE_THRESHOLD = 8'd8

)

(

    input wire clk,

    input wire rst,

    input wire enable,

    input wire [WIDTH-1:0] rand_set,

    input wire [WIDTH-1:0] rand_reset,

    input wire [WIDTH-1:0] rand_noise,

    input wire [WIDTH-1:0] rand_variation,

    output wire entropy_bit,

    output wire rram_state

);


//------------------------------------------------------
// RRAM State Registers
//------------------------------------------------------

reg rram_state_reg;

reg prev_state_reg;


//------------------------------------------------------
// Probability Threshold Registers
//------------------------------------------------------

reg [WIDTH-1:0] set_threshold_reg;

reg [WIDTH-1:0] reset_threshold_reg;

reg [WIDTH-1:0] noise_threshold_reg;


//------------------------------------------------------
// FSM Control Signals
//------------------------------------------------------

wire do_set;

wire do_reset;

wire do_read;

wire do_update;


//------------------------------------------------------
// Comparator Outputs
//------------------------------------------------------

wire set_success;

wire reset_success;


//------------------------------------------------------
// Cycle Variation Outputs
//------------------------------------------------------

wire [WIDTH-1:0] next_set_threshold;

wire [WIDTH-1:0] next_reset_threshold;


//------------------------------------------------------
// FSM
//------------------------------------------------------

rram_fsm FSM (

    .clk(clk),

    .rst(rst),

    .enable(enable),

    .do_set(do_set),

    .do_reset(do_reset),

    .do_read(do_read),

    .do_update(do_update)

);


//------------------------------------------------------
// SET Probability Comparator
//------------------------------------------------------

probability_compare #(

    .WIDTH(WIDTH)

)

SET_COMPARE (

    .rand_in(rand_set),

    .threshold(set_threshold_reg),

    .compare_result(set_success)

);


//------------------------------------------------------
// RESET Probability Comparator
//------------------------------------------------------

probability_compare #(

    .WIDTH(WIDTH)

)

RESET_COMPARE (

    .rand_in(rand_reset),

    .threshold(reset_threshold_reg),

    .compare_result(reset_success)

);


//------------------------------------------------------
// SET Cycle Variation
//------------------------------------------------------

cycle_variation #(

    .WIDTH(WIDTH)

)

SET_VARIATION (

    .current_threshold(set_threshold_reg),

    .rand_in(rand_variation),

    .next_threshold(next_set_threshold)

);


//------------------------------------------------------
// RESET Cycle Variation
//------------------------------------------------------

cycle_variation #(

    .WIDTH(WIDTH)

)

RESET_VARIATION (

    .current_threshold(reset_threshold_reg),

    .rand_in(rand_variation),

    .next_threshold(next_reset_threshold)

);


//------------------------------------------------------
// Transition Detection
//
// transition_bit = 1 only when the RRAM state
// changed between the previous clock and the
// current clock.
//
// This is intentionally combinational:
//
//     previous state XOR current state
//
//------------------------------------------------------

wire transition_bit;

assign transition_bit = prev_state_reg ^ rram_state_reg;


//------------------------------------------------------
// Sequential Register Update Logic
//------------------------------------------------------

always @(posedge clk or posedge rst)
begin

    if (rst)
    begin

        //--------------------------------------------------
        // Initialize RRAM State
        //--------------------------------------------------

        rram_state_reg <= 1'b0;     // HRS

        prev_state_reg <= 1'b0;


        //--------------------------------------------------
        // Initialize Thresholds
        //--------------------------------------------------

        set_threshold_reg   <= INIT_SET_THRESHOLD;

        reset_threshold_reg <= INIT_RESET_THRESHOLD;

        noise_threshold_reg <= INIT_NOISE_THRESHOLD;

    end

    else
    begin

        //--------------------------------------------------
        // Store Previous RRAM State
        //
        // IMPORTANT:
        // This must happen on EVERY clock cycle.
        //
        // Because non-blocking assignments are used,
        // transition_bit remains HIGH for the cycle
        // immediately following an actual state change.
        //--------------------------------------------------

        prev_state_reg <= rram_state_reg;


        //--------------------------------------------------
        // SET Operation
        //--------------------------------------------------

        if (enable && do_set && set_success)
        begin

            rram_state_reg <= 1'b1;     // LRS

        end


        //--------------------------------------------------
        // RESET Operation
        //--------------------------------------------------

        else if (enable && do_reset && reset_success)
        begin

            rram_state_reg <= 1'b0;     // HRS

        end


        //--------------------------------------------------
        // Threshold Update
        //--------------------------------------------------

        if (enable && do_update)
        begin

            set_threshold_reg   <= next_set_threshold;

            reset_threshold_reg <= next_reset_threshold;

        end

    end

end


//------------------------------------------------------
// RTN Engine
//------------------------------------------------------

wire entropy_internal;

rtn_engine #(

    .WIDTH(WIDTH)

)

RTN (

    .transition_bit(transition_bit),

    .rand_in(rand_noise),

    .noise_threshold(noise_threshold_reg),

    .entropy_bit(entropy_internal)

);


//------------------------------------------------------
// Entropy Output
//
// Entropy is only exposed during READ states.
//
// Outside READ:
//
//     entropy_bit = 0
//
// During READ:
//
//     entropy_bit = RTN output
//------------------------------------------------------

assign entropy_bit = do_read ? entropy_internal : 1'b0;


//------------------------------------------------------
// RRAM State Output
//------------------------------------------------------

assign rram_state = rram_state_reg;


endmodule
