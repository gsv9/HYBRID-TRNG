`timescale 1ns / 1ps

module tb_probability_compare;

    parameter WIDTH = 8;

    // DUT Inputs
    reg  [WIDTH-1:0] rand_in;
    reg  [WIDTH-1:0] threshold;

    // DUT Output
    wire compare_result;

    // Test Statistics
    integer pass_count = 0;
    integer fail_count = 0;

    //------------------------------------------------------
    // DUT (Device Under Test)
    //------------------------------------------------------

    probability_compare #(
        .WIDTH(WIDTH)
    ) DUT (
        .rand_in(rand_in),
        .threshold(threshold),
        .compare_result(compare_result)
    );

    //------------------------------------------------------
    // Test Task
    //------------------------------------------------------

    task run_test;

        input [WIDTH-1:0] rand_val;
        input [WIDTH-1:0] threshold_val;
        input expected_result;

        begin

            rand_in    = rand_val;
            threshold  = threshold_val;

            #10;

            if(compare_result === expected_result)
            begin
                pass_count = pass_count + 1;

                $display("[PASS] rand=%3d threshold=%3d -> result=%b",
                         rand_val,
                         threshold_val,
                         compare_result);
            end
            else
            begin
                fail_count = fail_count + 1;

                $display("[FAIL] rand=%3d threshold=%3d -> Expected=%b Got=%b",
                         rand_val,
                         threshold_val,
                         expected_result,
                         compare_result);
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
        $display(" Probability Comparator Verification");
        $display("==============================================");

        //--------------------------------------------------
        // Functional Tests
        //--------------------------------------------------

        run_test(8'd10 , 8'd100, 1'b1);
        run_test(8'd99 , 8'd100, 1'b1);
        run_test(8'd100, 8'd100, 1'b0);
        run_test(8'd101, 8'd100, 1'b0);

        //--------------------------------------------------
        // Boundary Tests
        //--------------------------------------------------

        run_test(8'd0  , 8'd0  , 1'b0);
        run_test(8'd0  , 8'd255, 1'b1);
        run_test(8'd255, 8'd255, 1'b0);
        run_test(8'd255, 8'd0  , 1'b0);

        //--------------------------------------------------
        // Mid-Range Tests
        //--------------------------------------------------

        run_test(8'd128, 8'd128, 1'b0);
        run_test(8'd127, 8'd128, 1'b1);
        run_test(8'd129, 8'd128, 1'b0);

        //--------------------------------------------------
        // Summary
        //--------------------------------------------------

        $display("");
        $display("==============================================");
        $display(" Verification Summary");
        $display("==============================================");
        $display(" Total Tests : %0d", pass_count + fail_count);
        $display(" Passed      : %0d", pass_count);
        $display(" Failed      : %0d", fail_count);

        if(fail_count == 0)
            $display(" RESULT : ALL TESTS PASSED");
        else
            $display(" RESULT : TEST FAILED");

        $display("==============================================");

        $finish;

    end

endmodule