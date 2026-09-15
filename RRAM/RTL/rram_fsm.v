module rram_fsm(

    input  wire clk,
    input  wire rst,
    input  wire enable,

    output reg do_set,
    output reg do_reset,
    output reg do_read,
    output reg do_update

);

    //--------------------------------------------------
    // State Encoding
    //--------------------------------------------------

localparam IDLE         = 3'd0,
           SET          = 3'd1,
           READ_SET     = 3'd2,
           UPDATE_SET   = 3'd3,
           RESET        = 3'd4,
           READ_RESET   = 3'd5,
           UPDATE_RESET = 3'd6;
    reg [2:0] state;
    reg [2:0] next_state;

    //--------------------------------------------------
    // State Register
    //--------------------------------------------------

always @(posedge clk or posedge rst)
begin
    if (rst)
        state <= IDLE;
    else if (enable || state != IDLE)
        state <= next_state;
end

    //--------------------------------------------------
    // Next State Logic
    //--------------------------------------------------
always @(*)
begin

    case(state)

        IDLE:
            if(enable)
                next_state = SET;
            else
                next_state = IDLE;

        SET:
            next_state = READ_SET;

        READ_SET:
            next_state = UPDATE_SET;

        UPDATE_SET:
            next_state = RESET;

        RESET:
            next_state = READ_RESET;

        READ_RESET:
            next_state = UPDATE_RESET;

        UPDATE_RESET:
            if(enable)
                next_state = SET;
            else
                next_state = IDLE;

        default:
            next_state = IDLE;

    endcase

end

    //--------------------------------------------------
    // Output Logic
    //--------------------------------------------------

always @(*)
begin

    do_set    = 1'b0;
    do_reset  = 1'b0;
    do_read   = 1'b0;
    do_update = 1'b0;

    case(state)

        SET:
            do_set = 1'b1;

        READ_SET:
            do_read = 1'b1;

        UPDATE_SET:
            do_update = 1'b1;

        RESET:
            do_reset = 1'b1;

        READ_RESET:
            do_read = 1'b1;

        UPDATE_RESET:
            do_update = 1'b1;

        default:
        begin
            do_set    = 1'b0;
            do_reset  = 1'b0;
            do_read   = 1'b0;
            do_update = 1'b0;
        end

    endcase

end

endmodule