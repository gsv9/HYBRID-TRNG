`timescale 1ns / 1ps

module tb_rram_cell;

    //------------------------------------------------------
    // Parameters
    //------------------------------------------------------

    parameter WIDTH = 8;

    //------------------------------------------------------
    // DUT Inputs
    //------------------------------------------------------

    reg clk;
    reg rst;
    reg enable;

    reg [WIDTH-1:0] rand_set;
    reg [WIDTH-1:0] rand_reset;
    reg [WIDTH-1:0] rand_noise;
    reg [WIDTH-1:0] rand_variation;

    //------------------------------------------------------
    // DUT Outputs
    //------------------------------------------------------

    wire entropy_bit;
    wire rram_state;

    //------------------------------------------------------
    // Test Statistics
    //------------------------------------------------------

    integer pass_count = 0;
    integer fail_count = 0;

    //------------------------------------------------------
    // DUT
    //------------------------------------------------------

    rram_cell #(
        .WIDTH(WIDTH),
        .INIT_SET_THRESHOLD(8'd145),
        .INIT_RESET_THRESHOLD(8'd110),
        .INIT_NOISE_THRESHOLD(8'd8)
    )
    DUT
    (
        .clk(clk),
        .rst(rst),
        .enable(enable),

        .rand_set(rand_set),
        .rand_reset(rand_reset),
        .rand_noise(rand_noise),
        .rand_variation(rand_variation),

        .entropy_bit(entropy_bit),
        .rram_state(rram_state)
    );

    //------------------------------------------------------
    // Clock Generation
    //------------------------------------------------------

    initial
        clk = 1'b0;

    always #5 clk = ~clk;

    //------------------------------------------------------
    // State Check Task
    //------------------------------------------------------

    task check_state;

        input expected_state;
        input [127:0] description;

        begin

            #1;

            if (rram_state === expected_state)
            begin

                pass_count = pass_count + 1;

                $display("[PASS] %-25s | RRAM_STATE=%b ENTROPY=%b",
                         description,
                         rram_state,
                         entropy_bit);

            end
            else
            begin

                fail_count = fail_count + 1;

                $display("[FAIL] %-25s | Expected STATE=%b Got STATE=%b",
                         description,
                         expected_state,
                         rram_state);

            end

        end

    endtask

    //------------------------------------------------------
    // Entropy Check Task
    //------------------------------------------------------

    task check_entropy;

        input expected_entropy;
        input [127:0] description;

        begin

            #1;

            if (entropy_bit === expected_entropy)
            begin

                pass_count = pass_count + 1;

                $display("[PASS] %-25s | ENTROPY=%b RRAM_STATE=%b",
                         description,
                         entropy_bit,
                         rram_state);

            end
            else
            begin

                fail_count = fail_count + 1;

                $display("[FAIL] %-25s | Expected ENTROPY=%b Got ENTROPY=%b",
                         description,
                         expected_entropy,
                         entropy_bit);

            end

        end

    endtask

    //------------------------------------------------------
    // Test Sequence
    //------------------------------------------------------

    initial
    begin

        $display("");
        $display("======================================================");
        $display(" RRAM CELL INTEGRATION VERIFICATION");
        $display("======================================================");

        //--------------------------------------------------
        // Initial Conditions
        //--------------------------------------------------

        enable         = 1'b0;

        rand_set       = 8'd0;
        rand_reset     = 8'd0;
        rand_noise     = 8'd255;
        rand_variation = 8'b00000001;

        //--------------------------------------------------
        // Reset
        //--------------------------------------------------

        rst = 1'b1;

        #12;

        //--------------------------------------------------
        // Verify Reset State
        //--------------------------------------------------

        check_state(1'b0, "Reset -> HRS");

        check_entropy(1'b0, "Reset -> Entropy OFF");

        //--------------------------------------------------
        // Release Reset
        //--------------------------------------------------

        rst = 1'b0;

        //--------------------------------------------------
        // Enable RRAM Cell
        //--------------------------------------------------

        enable = 1'b1;

        //--------------------------------------------------
        // SET OPERATION
        //--------------------------------------------------

        // Clock 1:
        // FSM moves from IDLE -> SET
        //
        // do_set becomes active after this edge.

        @(posedge clk);
        #1;

        $display("[INFO] FSM entered SET");

        //--------------------------------------------------
        // Clock 2:
        // RRAM cell sees do_set = 1
        // SET succeeds because:
        //
        // rand_set = 0
        // threshold = 145
        //
        // Therefore:
        //
        // 0 < 145 -> SET SUCCESS
        //
        // FSM moves SET -> READ_SET
        // RRAM state becomes LRS.
        //--------------------------------------------------

        @(posedge clk);
        #1;

        check_state(1'b1, "SET -> LRS");

        //--------------------------------------------------
        // READ_SET
        //--------------------------------------------------

        // At this point:
        //
        // previous state = 0
        // current state  = 1
        //
        // transition_bit = 1
        //
        // rand_noise = 255
        // noise threshold = 8
        //
        // 255 < 8 -> false
        //
        // entropy = 1 XOR 0 = 1

        check_entropy(1'b1, "READ_SET entropy");

        //--------------------------------------------------
        // UPDATE_SET
        //--------------------------------------------------

        @(posedge clk);
        #1;

        $display("[INFO] UPDATE_SET completed");

        //--------------------------------------------------
        // RESET OPERATION
        //--------------------------------------------------

        // FSM enters RESET

        @(posedge clk);
        #1;

        $display("[INFO] FSM entered RESET");

        //--------------------------------------------------
        // RRAM performs RESET
        //--------------------------------------------------

        // rand_reset = 0
        // reset threshold = 110
        //
        // 0 < 110 -> RESET SUCCESS
        //
        // FSM moves RESET -> READ_RESET
        // RRAM state becomes HRS.

        @(posedge clk);
        #1;

        check_state(1'b0, "RESET -> HRS");

        //--------------------------------------------------
        // READ_RESET
        //--------------------------------------------------

        // Previous state = 1
        // Current state  = 0
        //
        // transition_bit = 1
        //
        // No RTN flip.
        //
        // entropy = 1

        check_entropy(1'b1, "READ_RESET entropy");

        //--------------------------------------------------
        // UPDATE_RESET
        //--------------------------------------------------

        @(posedge clk);
        #1;

        $display("[INFO] UPDATE_RESET completed");

        //--------------------------------------------------
        // SECOND SET
        //--------------------------------------------------

        // FSM enters SET

        @(posedge clk);
        #1;

        $display("[INFO] FSM entered second SET");

        //--------------------------------------------------
        // RRAM performs second SET
        //--------------------------------------------------

        @(posedge clk);
        #1;

        check_state(1'b1, "Second SET -> LRS");

        //--------------------------------------------------
        // Verify entropy during current READ_SET
        //--------------------------------------------------

        check_entropy(1'b1, "Second READ_SET entropy");

        //--------------------------------------------------
        // Disable Cell
        //--------------------------------------------------

        enable = 1'b0;

        //--------------------------------------------------
        // Allow FSM to complete current sequence
        // and return to IDLE.
        //--------------------------------------------------

        repeat(4)
            @(posedge clk);

        #1;

        //--------------------------------------------------
        // Entropy should be inactive after returning
        // to IDLE.
        //--------------------------------------------------

        check_entropy(1'b0, "IDLE -> Entropy OFF");

        //--------------------------------------------------
        // Summary
        //--------------------------------------------------

        $display("");
        $display("======================================================");
        $display(" Verification Summary");
        $display("======================================================");

        $display("Total Tests : %0d",
                 pass_count + fail_count);

        $display("Passed      : %0d",
                 pass_count);

        $display("Failed      : %0d",
                 fail_count);

        if (fail_count == 0)
        begin

            $display("RESULT : ALL TESTS PASSED");

        end
        else
        begin

            $display("RESULT : TEST FAILED");

        end

        $display("======================================================");

        $finish;

    end

endmodule