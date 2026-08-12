`timescale 1ns / 1ps

module tb_rtn_engine;

    //------------------------------------------------------
    // Parameters
    //------------------------------------------------------

    parameter WIDTH = 8;

    //------------------------------------------------------
    // DUT Inputs
    //------------------------------------------------------

    reg transition_bit;
    reg [WIDTH-1:0] rand_in;
    reg [WIDTH-1:0] noise_threshold;

    //------------------------------------------------------
    // DUT Output
    //------------------------------------------------------

    wire entropy_bit;

    //------------------------------------------------------
    // Test Statistics
    //------------------------------------------------------

    integer pass_count = 0;
    integer fail_count = 0;

    //------------------------------------------------------
    // DUT
    //------------------------------------------------------

    rtn_engine #(
        .WIDTH(WIDTH)
    )
    DUT
    (
        .transition_bit(transition_bit),
        .rand_in(rand_in),
        .noise_threshold(noise_threshold),
        .entropy_bit(entropy_bit)
    );

    //------------------------------------------------------
    // Test Task
    //------------------------------------------------------

    task run_test;

        input transition;
        input [WIDTH-1:0] random;
        input [WIDTH-1:0] threshold;
        input expected;

        begin

            transition_bit = transition;
            rand_in = random;
            noise_threshold = threshold;

            #10;

            if(entropy_bit === expected)
            begin
                pass_count = pass_count + 1;

                $display("[PASS] Transition=%b Rand=%3d Threshold=%3d Entropy=%b",
                         transition,
                         random,
                         threshold,
                         entropy_bit);
            end
            else
            begin
                fail_count = fail_count + 1;

                $display("[FAIL] Transition=%b Rand=%3d Threshold=%3d Expected=%b Got=%b",
                         transition,
                         random,
                         threshold,
                         expected,
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
        $display("==============================================");
        $display(" RTN Engine Verification");
        $display("==============================================");

        // Flip occurs
        run_test(0, 8'd10 , 8'd100, 1'b1);
        run_test(1, 8'd10 , 8'd100, 1'b0);

        // No flip
        run_test(0, 8'd150, 8'd100, 1'b0);
        run_test(1, 8'd150, 8'd100, 1'b1);

        // Always flip
        run_test(0, 8'd0  , 8'd255, 1'b1);

        // Boundary cases
        run_test(1, 8'd255, 8'd255, 1'b1);
        run_test(1, 8'd0  , 8'd0  , 1'b1);
        run_test(0, 8'd255, 8'd0  , 1'b0);

        //--------------------------------------------------
        // Summary
        //--------------------------------------------------

        $display("");
        $display("==============================================");
        $display(" Verification Summary");
        $display("==============================================");

        $display("Total Tests : %0d", pass_count + fail_count);
        $display("Passed      : %0d", pass_count);
        $display("Failed      : %0d", fail_count);

        if(fail_count == 0)
            $display("RESULT : ALL TESTS PASSED");
        else
            $display("RESULT : TEST FAILED");

        $display("==============================================");

        $finish;

    end

endmodule