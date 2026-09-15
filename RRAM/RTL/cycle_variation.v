module cycle_variation
#(

    parameter WIDTH = 8,

    parameter MIN_THRESHOLD = 8'd80,

    parameter MAX_THRESHOLD = 8'd180

)

(

    input  wire [WIDTH-1:0] current_threshold,

    input  wire [WIDTH-1:0] rand_in,

    output reg  [WIDTH-1:0] next_threshold

);

always @(*)

begin

    // Default

    next_threshold = current_threshold;

    case(rand_in[1:0])

        //-----------------------------------
        // Decrement
        //-----------------------------------

        2'b00:

        begin

            if(current_threshold > MIN_THRESHOLD)

                next_threshold = current_threshold - 1;

        end

        //-----------------------------------
        // No Change
        //-----------------------------------

        2'b01:

        begin

            next_threshold = current_threshold;

        end

        //-----------------------------------
        // Increment
        //-----------------------------------

        2'b10:

        begin

            if(current_threshold < MAX_THRESHOLD)

                next_threshold = current_threshold + 1;

        end

        //-----------------------------------
        // No Change
        //-----------------------------------

        2'b11:

        begin

            next_threshold = current_threshold;

        end

    endcase

end

endmodule