`timescale 1ns / 1ps

module tb_rram_fsm;

    //------------------------------------------------------
    // DUT Inputs
    //------------------------------------------------------

    reg clk;
    reg rst;
    reg enable;

    //------------------------------------------------------
    // DUT Outputs
    //------------------------------------------------------

    wire do_set;
    wire do_reset;
    wire do_read;
    wire do_update;

    //------------------------------------------------------
    // Statistics
    //------------------------------------------------------

    integer pass_count = 0;
    integer fail_count = 0;

    //------------------------------------------------------
    // DUT
    //------------------------------------------------------

    rram_fsm DUT
    (
        .clk(clk),
        .rst(rst),
        .enable(enable),

        .do_set(do_set),
        .do_reset(do_reset),
        .do_read(do_read),
        .do_update(do_update)
    );

    //------------------------------------------------------
    // Clock Generation
    //------------------------------------------------------

    initial
        clk = 0;

    always #5 clk = ~clk;

    //------------------------------------------------------
    // Verification Task
    //------------------------------------------------------

    task check_outputs;

        input expected_set;
        input expected_reset;
        input expected_read;
        input expected_update;
        input [127:0] state_name;

        begin

            @(posedge clk);
            #1;

            if ((do_set    === expected_set) &&
                (do_reset  === expected_reset) &&
                (do_read   === expected_read) &&
                (do_update === expected_update))
            begin

                pass_count = pass_count + 1;

                $display("[PASS] %-12s | SET=%b RESET=%b READ=%b UPDATE=%b",
                         state_name,
                         do_set,
                         do_reset,
                         do_read,
                         do_update);

            end
            else
            begin

                fail_count = fail_count + 1;

                $display("[FAIL] %-12s", state_name);

                $display("       Expected : %b %b %b %b",
                         expected_set,
                         expected_reset,
                         expected_read,
                         expected_update);

                $display("       Got      : %b %b %b %b",
                         do_set,
                         do_reset,
                         do_read,
                         do_update);

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
        $display(" RRAM FSM Verification");
        $display("==============================================");

        //--------------------------------------------------
        // Reset
        //--------------------------------------------------

        rst = 1;
        enable = 0;

        #12;

        rst = 0;

        //--------------------------------------------------
        // Verify IDLE
        //--------------------------------------------------

        check_outputs(0,0,0,0,"IDLE");

        //--------------------------------------------------
        // Enable FSM
        //--------------------------------------------------

        enable = 1;

        check_outputs(1,0,0,0,"SET");

        check_outputs(0,0,1,0,"READ_SET");

        check_outputs(0,0,0,1,"UPDATE_SET");

        check_outputs(0,1,0,0,"RESET");

        check_outputs(0,0,1,0,"READ_RESET");

        check_outputs(0,0,0,1,"UPDATE_RESET");

        //--------------------------------------------------
        // Verify Loop
        //--------------------------------------------------

        check_outputs(1,0,0,0,"SET");

        //--------------------------------------------------
        // Disable
        //--------------------------------------------------

        enable = 0;

        repeat(2)
            @(posedge clk);

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