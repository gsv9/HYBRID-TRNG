module tb_cycle_variation;

    //------------------------------------------------------
    // Parameters
    //------------------------------------------------------

    parameter WIDTH = 8;

    parameter MIN_THRESHOLD = 8'd80;
    parameter MAX_THRESHOLD = 8'd180;

    //------------------------------------------------------
    // DUT Inputs
    //------------------------------------------------------

    reg  [WIDTH-1:0] current_threshold;
    reg  [WIDTH-1:0] rand_in;

    //------------------------------------------------------
    // DUT Output
    //------------------------------------------------------

    wire [WIDTH-1:0] next_threshold;

    //------------------------------------------------------
    // Test Statistics
    //------------------------------------------------------

    integer pass_count = 0;
    integer fail_count = 0;

    //------------------------------------------------------
    // DUT
    //------------------------------------------------------

    cycle_variation #(

        .WIDTH(WIDTH),
        .MIN_THRESHOLD(MIN_THRESHOLD),
        .MAX_THRESHOLD(MAX_THRESHOLD)

    )

    DUT (

        .current_threshold(current_threshold),
        .rand_in(rand_in),
        .next_threshold(next_threshold)

    );

    //------------------------------------------------------
    // Test Task
    //------------------------------------------------------

    task run_test;

        input [WIDTH-1:0] current;
        input [WIDTH-1:0] random;
        input [WIDTH-1:0] expected;

        begin

            current_threshold = current;
            rand_in           = random;

            #10;

            if(next_threshold === expected)
            begin

                pass_count = pass_count + 1;

                $display("[PASS] Current=%3d  Rand=%2b  Next=%3d",
                         current,
                         random[1:0],
                         next_threshold);

            end

            else
            begin

                fail_count = fail_count + 1;

                $display("[FAIL] Current=%3d Rand=%2b Expected=%3d Got=%3d",
                         current,
                         random[1:0],
                         expected,
                         next_threshold);

            end

        end

    endtask

    //------------------------------------------------------
    // Test Sequence
    //------------------------------------------------------

    initial
    begin

        $display("");
        $display("==================================================");
        $display(" Cycle Variation Verification");
        $display("==================================================");

        //--------------------------------------------------
        // Normal Operation
        //--------------------------------------------------

        // Decrement
        run_test(8'd100, 8'b00000000, 8'd99);

        // No Change
        run_test(8'd100, 8'b00000001, 8'd100);

        // Increment
        run_test(8'd100, 8'b00000010, 8'd101);

        // No Change
        run_test(8'd100, 8'b00000011, 8'd100);

        //--------------------------------------------------
        // Lower Boundary
        //--------------------------------------------------

        // Already at minimum
        run_test(MIN_THRESHOLD, 8'b00000000, MIN_THRESHOLD);

        //--------------------------------------------------
        // Upper Boundary
        //--------------------------------------------------

        // Already at maximum
        run_test(MAX_THRESHOLD, 8'b00000010, MAX_THRESHOLD);

        //--------------------------------------------------
        // Boundary Crossing Checks
        //--------------------------------------------------

        run_test(8'd81, 8'b00000000, 8'd80);

        run_test(8'd179, 8'b00000010, 8'd180);

        //--------------------------------------------------
        // Additional Random Cases
        //--------------------------------------------------

        run_test(8'd150, 8'b11111110, 8'd151);

        run_test(8'd150, 8'b11111100, 8'd149);

        run_test(8'd150, 8'b11111101, 8'd150);

        run_test(8'd150, 8'b11111111, 8'd150);

        //--------------------------------------------------
        // Summary
        //--------------------------------------------------

        $display("");
        $display("==================================================");
        $display(" Verification Summary");
        $display("==================================================");

        $display("Total Tests : %0d", pass_count + fail_count);
        $display("Passed      : %0d", pass_count);
        $display("Failed      : %0d", fail_count);

        if(fail_count == 0)
            $display("RESULT : ALL TESTS PASSED");
        else
            $display("RESULT : TEST FAILED");

        $display("==================================================");

        $finish;

    end

endmodule