`timescale 1ns / 1ps

module tb_rram_cell_stochastic;

    //------------------------------------------------------
    // Parameters
    //------------------------------------------------------

    parameter WIDTH = 8;

    parameter NUM_RUNS = 5;

    parameter NUM_READ_SAMPLES = 100000;

    parameter MAX_CYCLES = 500000;

    //------------------------------------------------------
    // RRAM Model Parameters
    //------------------------------------------------------

    parameter INIT_SET_THRESHOLD   = 8'd145;
    parameter INIT_RESET_THRESHOLD = 8'd110;
    parameter INIT_NOISE_THRESHOLD = 8'd96;


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
    // LFSR Registers
    //------------------------------------------------------

    reg [7:0] lfsr_set;
    reg [7:0] lfsr_reset;
    reg [7:0] lfsr_noise;
    reg [7:0] lfsr_variation;


    //------------------------------------------------------
    // Statistics
    //------------------------------------------------------

    integer entropy_ones;
    integer entropy_zeros;

    integer set_transitions;
    integer reset_transitions;

    integer read_count;
    integer total_cycles;

    integer transition_ones;
    integer transition_zeros;

    integer rtn_flips;

    integer entropy_mismatch;


    //------------------------------------------------------
    // Run Control
    //------------------------------------------------------

    integer current_run;
    integer run_seed;

    integer file_handle;

    integer completed_runs;


    //------------------------------------------------------
    // Previous RRAM State
    //------------------------------------------------------

    reg previous_rram_state;


    //------------------------------------------------------
    // DUT
    //------------------------------------------------------

    rram_cell #(

        .WIDTH(WIDTH),

        .INIT_SET_THRESHOLD(INIT_SET_THRESHOLD),

        .INIT_RESET_THRESHOLD(INIT_RESET_THRESHOLD),

        .INIT_NOISE_THRESHOLD(INIT_NOISE_THRESHOLD)

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
    // LFSR Function
    //------------------------------------------------------

    function [7:0] next_lfsr;

        input [7:0] current_lfsr;

        begin

            next_lfsr = {

                current_lfsr[6:0],

                current_lfsr[7] ^
                current_lfsr[5] ^
                current_lfsr[4] ^
                current_lfsr[3]

            };

        end

    endfunction


    //------------------------------------------------------
    // Statistics Collection
    //
    // Statistics are collected after DUT clock edge.
    //------------------------------------------------------

    always @(posedge clk)
    begin

        #1;

        if (!rst)
        begin

            total_cycles = total_cycles + 1;


            //--------------------------------------------------
            // RRAM State Transition Detection
            //--------------------------------------------------

            if ((previous_rram_state == 1'b0) &&
                (rram_state == 1'b1))
            begin

                set_transitions = set_transitions + 1;

            end

            else if ((previous_rram_state == 1'b1) &&
                     (rram_state == 1'b0))
            begin

                reset_transitions = reset_transitions + 1;

            end

            previous_rram_state = rram_state;


            //--------------------------------------------------
            // READ Sampling
            //--------------------------------------------------

            if (DUT.do_read)
            begin

                read_count = read_count + 1;


                //--------------------------------------------------
                // Transition Bit Statistics
                //--------------------------------------------------

                if (DUT.transition_bit == 1'b1)
                    transition_ones = transition_ones + 1;
                else
                    transition_zeros = transition_zeros + 1;


                //--------------------------------------------------
                // RTN Statistics
                //--------------------------------------------------

                if (DUT.RTN.flip_enable == 1'b1)
                    rtn_flips = rtn_flips + 1;


                //--------------------------------------------------
                // Entropy Statistics
                //--------------------------------------------------

                if (entropy_bit == 1'b1)
                    entropy_ones = entropy_ones + 1;

                else if (entropy_bit == 1'b0)
                    entropy_zeros = entropy_zeros + 1;


                //--------------------------------------------------
                // Entropy File
                //--------------------------------------------------

                if (file_handle != 0)
                begin

                    $fwrite(file_handle, "%b\n", entropy_bit);

                end


                //--------------------------------------------------
                // Verify XOR Entropy Logic
                //--------------------------------------------------

                if (entropy_bit !==
                    (DUT.transition_bit ^ DUT.RTN.entropy_noise_bit))
                begin

                    entropy_mismatch = entropy_mismatch + 1;

                end

            end

        end

    end


    //------------------------------------------------------
    // Main Test
    //------------------------------------------------------

    initial
    begin

        //--------------------------------------------------
        // Initial Conditions
        //--------------------------------------------------

        rst = 1'b1;

        enable = 1'b0;

        rand_set       = 8'd0;
        rand_reset     = 8'd0;
        rand_noise     = 8'd0;
        rand_variation = 8'd0;


        //--------------------------------------------------
        // Clear Statistics
        //--------------------------------------------------

        entropy_ones = 0;
        entropy_zeros = 0;

        set_transitions = 0;
        reset_transitions = 0;

        read_count = 0;
        total_cycles = 0;

        transition_ones = 0;
        transition_zeros = 0;

        rtn_flips = 0;

        entropy_mismatch = 0;

        previous_rram_state = 1'b0;

        completed_runs = 0;

        file_handle = 0;


        //--------------------------------------------------
        // Initial Reset
        //--------------------------------------------------

        #20;

        rst = 1'b0;

        #10;


        //--------------------------------------------------
        // MULTIPLE RUN LOOP
        //--------------------------------------------------

        for (current_run = 1;
             current_run <= NUM_RUNS;
             current_run = current_run + 1)
        begin

            //------------------------------------------------
            // Display Run Information
            //------------------------------------------------

            $display("");
            $display("======================================================");
            $display(" STARTING RRAM STOCHASTIC RUN %0d", current_run);
            $display("======================================================");


            //------------------------------------------------
            // Reset RRAM Before Each Run
            //------------------------------------------------

            enable = 1'b0;

            rst = 1'b1;

            #20;

            rst = 1'b0;

            #10;


            //------------------------------------------------
            // Generate DIFFERENT Seeds
            //
            // Every run receives four different LFSR
            // starting states.
            //------------------------------------------------

            run_seed = 8'd37 * current_run;


            lfsr_set =
                8'hA5 ^
                (run_seed + 8'h11);

            lfsr_reset =
                8'hC3 ^
                (run_seed + 8'h27);

            lfsr_noise =
                8'hE7 ^
                (run_seed + 8'h43);

            lfsr_variation =
                8'h9B ^
                (run_seed + 8'h65);


            //------------------------------------------------
            // Prevent Zero LFSR Seeds
            //------------------------------------------------

            if (lfsr_set == 8'd0)
                lfsr_set = 8'hA5;

            if (lfsr_reset == 8'd0)
                lfsr_reset = 8'hC3;

            if (lfsr_noise == 8'd0)
                lfsr_noise = 8'hE7;

            if (lfsr_variation == 8'd0)
                lfsr_variation = 8'h9B;


            //------------------------------------------------
            // Load Random Inputs
            //------------------------------------------------

            rand_set       = lfsr_set;
            rand_reset     = lfsr_reset;
            rand_noise     = lfsr_noise;
            rand_variation = lfsr_variation;


            //------------------------------------------------
            // Reset Run Statistics
            //------------------------------------------------

            entropy_ones = 0;
            entropy_zeros = 0;

            set_transitions = 0;
            reset_transitions = 0;

            read_count = 0;
            total_cycles = 0;

            transition_ones = 0;
            transition_zeros = 0;

            rtn_flips = 0;

            entropy_mismatch = 0;

            previous_rram_state = 1'b0;


            //------------------------------------------------
            // Open Run-Specific Entropy File
            //------------------------------------------------

            if (current_run == 1)
                file_handle = $fopen("rram_entropy_run1.txt", "w");

            else if (current_run == 2)
                file_handle = $fopen("rram_entropy_run2.txt", "w");

            else if (current_run == 3)
                file_handle = $fopen("rram_entropy_run3.txt", "w");

            else if (current_run == 4)
                file_handle = $fopen("rram_entropy_run4.txt", "w");

            else if (current_run == 5)
                file_handle = $fopen("rram_entropy_run5.txt", "w");


            //------------------------------------------------
            // Check File
            //------------------------------------------------

            if (file_handle == 0)
            begin

                $display("[ERROR] Could not open entropy file for Run %0d",
                         current_run);

            end

            else
            begin

                $display("[INFO] Entropy file opened for Run %0d",
                         current_run);

            end


            //------------------------------------------------
            // Enable RRAM
            //------------------------------------------------

            enable = 1'b1;


            //------------------------------------------------
            // Run Until Required Samples Are Collected
            //------------------------------------------------

            while ((read_count < NUM_READ_SAMPLES) &&
                   (total_cycles < MAX_CYCLES))
            begin

                @(posedge clk);

            end


            //------------------------------------------------
            // Stop RRAM
            //------------------------------------------------

            enable = 1'b0;


            //------------------------------------------------
            // Close Entropy File
            //------------------------------------------------

            if (file_handle != 0)
            begin

                $fclose(file_handle);

                file_handle = 0;

                $display("[INFO] Entropy file closed for Run %0d",
                         current_run);

            end


            //------------------------------------------------
            // Run Statistics
            //------------------------------------------------

            $display("");
            $display("------------------------------------------------------");
            $display(" RRAM RUN %0d RESULTS", current_run);
            $display("------------------------------------------------------");

            $display("Seed Base               : %0d", run_seed);

            $display("Total Clock Cycles      : %0d",
                     total_cycles);

            $display("Total Read Samples      : %0d",
                     read_count);

            $display("Entropy 0 Count         : %0d",
                     entropy_zeros);

            $display("Entropy 1 Count         : %0d",
                     entropy_ones);

            $display("HRS -> LRS Transitions  : %0d",
                     set_transitions);

            $display("LRS -> HRS Transitions  : %0d",
                     reset_transitions);

            $display("Transition 0 Count      : %0d",
                     transition_zeros);

            $display("Transition 1 Count      : %0d",
                     transition_ones);

            $display("RTN Flip Count           : %0d",
                     rtn_flips);

            $display("Entropy Logic Mismatches : %0d",
                     entropy_mismatch);


            //------------------------------------------------
            // Probability Calculations
            //------------------------------------------------

            if (read_count > 0)
            begin

                $display("Entropy 1 Probability    : %f",
                    entropy_ones * 1.0 / read_count);

                $display("Entropy 0 Probability    : %f",
                    entropy_zeros * 1.0 / read_count);

                $display("Absolute Bias            : %f",
                    (entropy_ones * 1.0 / read_count) > 0.5 ?
                    ((entropy_ones * 1.0 / read_count) - 0.5) :
                    (0.5 - (entropy_ones * 1.0 / read_count)));

                $display("Transition 1 Probability : %f",
                    transition_ones * 1.0 / read_count);

                $display("Observed RTN Probability : %f",
                    rtn_flips * 1.0 / read_count);

            end


            //------------------------------------------------
            // Verification
            //------------------------------------------------

            $display("");
            $display(" Stochastic Verification Checks");
            $display("------------------------------------------------------");


            if (read_count >= NUM_READ_SAMPLES)
            begin

                $display("[PASS] Required read samples collected");

            end

            else
            begin

                $display("[FAIL] Required read samples NOT collected");

            end


            if ((entropy_ones > 0) &&
                (entropy_zeros > 0))
            begin

                $display("[PASS] Entropy '0' and '1' samples observed");

            end

            else
            begin

                $display("[FAIL] Both entropy values not observed");

            end


            if (set_transitions > 0)
            begin

                $display("[PASS] HRS -> LRS transitions observed");

            end

            else
            begin

                $display("[FAIL] HRS -> LRS transitions missing");

            end


            if (reset_transitions > 0)
            begin

                $display("[PASS] LRS -> HRS transitions observed");

            end

            else
            begin

                $display("[FAIL] LRS -> HRS transitions missing");

            end


            if ((transition_ones > 0) &&
                (transition_zeros > 0))
            begin

                $display("[PASS] Both transition-bit values observed");

            end

            else
            begin

                $display("[FAIL] Both transition-bit values not observed");

            end


            if (rtn_flips > 0)
            begin

                $display("[PASS] RTN flip events observed");

            end

            else
            begin

                $display("[FAIL] RTN flip events not observed");

            end


            if (entropy_mismatch == 0)
            begin

                $display("[PASS] Entropy XOR logic verified");

            end

            else
            begin

                $display("[FAIL] Entropy XOR logic mismatch detected");

            end


            //------------------------------------------------
            // Mark Run Complete
            //------------------------------------------------

            completed_runs = completed_runs + 1;


            //------------------------------------------------
            // Small Gap Before Next Run
            //------------------------------------------------

            #20;

        end


        //------------------------------------------------------
        // Final Summary
        //------------------------------------------------------

        $display("");
        $display("======================================================");
        $display(" ALL RRAM STOCHASTIC RUNS COMPLETED");
        $display("======================================================");

        $display("Completed Runs : %0d / %0d",
                 completed_runs,
                 NUM_RUNS);

        $display("");
        $display("Generated Entropy Files:");
        $display("  rram_entropy_run1.txt");
        $display("  rram_entropy_run2.txt");
        $display("  rram_entropy_run3.txt");
        $display("  rram_entropy_run4.txt");
        $display("  rram_entropy_run5.txt");

        $display("");
        $display("NEXT STEP:");
        $display("Analyze all five bitstreams using Python.");
        $display("======================================================");


        #100;

        $finish;

    end


    //------------------------------------------------------
    // LFSR Update
    //
    // Negative edge is used so that new random values are
    // available before the next positive DUT edge.
    //------------------------------------------------------

    always @(negedge clk)
    begin

        if (!rst && enable)
        begin

            lfsr_set       <= next_lfsr(lfsr_set);
            lfsr_reset     <= next_lfsr(lfsr_reset);
            lfsr_noise     <= next_lfsr(lfsr_noise);
            lfsr_variation <= next_lfsr(lfsr_variation);


            rand_set       <= next_lfsr(lfsr_set);
            rand_reset     <= next_lfsr(lfsr_reset);
            rand_noise     <= next_lfsr(lfsr_noise);
            rand_variation <= next_lfsr(lfsr_variation);

        end

    end

endmodule