`timescale 1ns / 1ps

module tb_rram_cell_stochastic;

    //------------------------------------------------------
    // Parameters
    //------------------------------------------------------

    parameter WIDTH = 8;

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
    // Entropy Bitstream Storage
    //
    // Stores every entropy bit generated during READ.
    //------------------------------------------------------

    reg entropy_bitstream [0:NUM_READ_SAMPLES-1];


    //------------------------------------------------------
    // Output File Handle
    //------------------------------------------------------

    integer entropy_file;


    //------------------------------------------------------
    // Entropy Statistics
    //------------------------------------------------------

    integer entropy_ones;
    integer entropy_zeros;


    //------------------------------------------------------
    // RRAM State Transition Statistics
    //------------------------------------------------------

    integer set_transitions;
    integer reset_transitions;


    //------------------------------------------------------
    // READ Statistics
    //------------------------------------------------------

    integer read_count;
    integer total_cycles;


    //------------------------------------------------------
    // Transition Bit Statistics
    //------------------------------------------------------

    integer transition_ones;
    integer transition_zeros;


    //------------------------------------------------------
    // RTN Statistics
    //------------------------------------------------------

    integer rtn_flips;


    //------------------------------------------------------
    // Entropy Logic Verification
    //------------------------------------------------------

    integer entropy_mismatch;


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
    // Statistics are collected after the DUT clock edge.
    //------------------------------------------------------

    always @(posedge clk)
    begin
    
        #1;

        if (!rst)
        begin

            //--------------------------------------------------
            // Total Clock Cycles
            //--------------------------------------------------

            total_cycles = total_cycles + 1;


            //--------------------------------------------------
            // Detect RRAM State Transitions
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


            //--------------------------------------------------
            // Store Current RRAM State
            //--------------------------------------------------

            previous_rram_state = rram_state;


            //--------------------------------------------------
            // READ Statistics
            //--------------------------------------------------

            if (DUT.do_read)
            begin

                //--------------------------------------------------
                // Store Entropy Bit
                //--------------------------------------------------

                if (read_count < NUM_READ_SAMPLES)
                begin

                    entropy_bitstream[read_count] = entropy_bit;

                end


                //--------------------------------------------------
                // Increment Read Counter
                //--------------------------------------------------

                read_count = read_count + 1;


                //--------------------------------------------------
                // Transition Bit Statistics
                //--------------------------------------------------

                if (DUT.transition_bit == 1'b1)
                begin

                    transition_ones = transition_ones + 1;

                end

                else if (DUT.transition_bit == 1'b0)
                begin

                    transition_zeros = transition_zeros + 1;

                end


                //--------------------------------------------------
                // RTN Flip Statistics
                //--------------------------------------------------

                if (DUT.RTN.flip_enable == 1'b1)
                begin

                    rtn_flips = rtn_flips + 1;

                end


                //--------------------------------------------------
                // Entropy Statistics
                //--------------------------------------------------

                if (entropy_bit == 1'b1)
                begin

                    entropy_ones = entropy_ones + 1;

                end

                else if (entropy_bit == 1'b0)
                begin

                    entropy_zeros = entropy_zeros + 1;

                end


                //--------------------------------------------------
                // Verify Entropy Equation
                //
                // entropy_bit =
                // transition_bit XOR flip_enable
                //--------------------------------------------------

                if (entropy_bit !==
                    (DUT.transition_bit ^ DUT.RTN.flip_enable))
                begin

                    entropy_mismatch = entropy_mismatch + 1;

                end

            end

        end

    end


    //------------------------------------------------------
    // Random Input Update
    //
    // Random values are updated on the negative edge so
    // that they remain stable before the next positive
    // edge where the DUT operates.
    //------------------------------------------------------

    always @(negedge clk)
    begin

        if (!rst)
        begin

            //--------------------------------------------------
            // Advance LFSRs
            //--------------------------------------------------

            lfsr_set       = next_lfsr(lfsr_set);

            lfsr_reset     = next_lfsr(lfsr_reset);

            lfsr_noise     = next_lfsr(lfsr_noise);

            lfsr_variation = next_lfsr(lfsr_variation);


            //--------------------------------------------------
            // Apply New Random Values
            //--------------------------------------------------

            rand_set       = lfsr_set;

            rand_reset     = lfsr_reset;

            rand_noise     = lfsr_noise;

            rand_variation = lfsr_variation;

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

        rst    = 1'b1;

        enable = 1'b0;


        //--------------------------------------------------
        // LFSR Seeds
        //--------------------------------------------------

        lfsr_set       = 8'b10110101;

        lfsr_reset     = 8'b11001011;

        lfsr_noise     = 8'b11100011;

        lfsr_variation = 8'b10010111;


        //--------------------------------------------------
        // Initial Random Values
        //--------------------------------------------------

        rand_set       = lfsr_set;

        rand_reset     = lfsr_reset;

        rand_noise     = lfsr_noise;

        rand_variation = lfsr_variation;


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


        //--------------------------------------------------
        // Reset DUT
        //--------------------------------------------------

        #20;

        rst = 1'b0;


        //--------------------------------------------------
        // Enable RRAM
        //--------------------------------------------------

        enable = 1'b1;


        //--------------------------------------------------
        // Run Until Required Number of READ Samples
        //--------------------------------------------------

        while ((read_count < NUM_READ_SAMPLES) &&
               (total_cycles < MAX_CYCLES))
        begin

            @(posedge clk);

        end


        //--------------------------------------------------
        // Disable RRAM
        //--------------------------------------------------

        enable = 1'b0;


        //--------------------------------------------------
        // Final Delay
        //--------------------------------------------------

        #20;


        //--------------------------------------------------
        // Open Entropy Bitstream File
        //--------------------------------------------------

        entropy_file = $fopen(
            "rram_entropy_100k.txt",
            "w"
        );


        //--------------------------------------------------
        // Check File Open
        //--------------------------------------------------

        if (entropy_file == 0)
        begin

            $display("");
            $display("[ERROR] Could not open entropy output file");

        end

        else
        begin

            //--------------------------------------------------
            // Write Entropy Bitstream
            //
            // One entropy bit per line.
            //--------------------------------------------------

            for (integer i = 0;
                 i < read_count && i < NUM_READ_SAMPLES;
                 i = i + 1)
            begin

                $fwrite(
                    entropy_file,
                    "%0d\n",
                    entropy_bitstream[i]
                );

            end


            //--------------------------------------------------
            // Close File
            //--------------------------------------------------

            $fclose(entropy_file);


            $display("");
            $display("[INFO] Entropy bitstream written to:");
            $display("       rram_entropy_100k.txt");

        end


        //------------------------------------------------------
        // Results
        //------------------------------------------------------

        $display("");

        $display("======================================================");

        $display(" RRAM STOCHASTIC VERIFICATION");

        $display("======================================================");


        //--------------------------------------------------
        // Configuration
        //--------------------------------------------------

        $display("SET Threshold            : %0d",
                 INIT_SET_THRESHOLD);

        $display("RESET Threshold          : %0d",
                 INIT_RESET_THRESHOLD);

        $display("RTN Noise Threshold      : %0d",
                 INIT_NOISE_THRESHOLD);


        //--------------------------------------------------
        // Basic Counts
        //--------------------------------------------------

        $display("");

        $display("Total Clock Cycles       : %0d",
                 total_cycles);

        $display("Total Read Samples       : %0d",
                 read_count);


        //--------------------------------------------------
        // Entropy Counts
        //--------------------------------------------------

        $display("Entropy 0 Count          : %0d",
                 entropy_zeros);

        $display("Entropy 1 Count          : %0d",
                 entropy_ones);


        //--------------------------------------------------
        // RRAM State Transitions
        //--------------------------------------------------

        $display("HRS -> LRS Transitions   : %0d",
                 set_transitions);

        $display("LRS -> HRS Transitions   : %0d",
                 reset_transitions);


        //--------------------------------------------------
        // Transition Bit Statistics
        //--------------------------------------------------

        $display("Transition 0 Count       : %0d",
                 transition_zeros);

        $display("Transition 1 Count       : %0d",
                 transition_ones);


        //--------------------------------------------------
        // RTN Statistics
        //--------------------------------------------------

        $display("RTN Flip Count           : %0d",
                 rtn_flips);


        //--------------------------------------------------
        // Entropy Logic Verification
        //--------------------------------------------------

        $display("Entropy Logic Mismatches : %0d",
                 entropy_mismatch);


        //--------------------------------------------------
        // Probability Calculations
        //--------------------------------------------------

        if (read_count > 0)
        begin

            $display("");

            $display("Entropy 1 Probability    : %f",

                     entropy_ones * 1.0 /
                     read_count);


            $display("Entropy 0 Probability    : %f",

                     entropy_zeros * 1.0 /
                     read_count);


            //--------------------------------------------------
            // Absolute Bias
            //--------------------------------------------------

            if ((entropy_ones * 1.0 / read_count) >= 0.5)
            begin

                $display("Absolute Bias            : %f",

                         (entropy_ones * 1.0 /
                          read_count) - 0.5);

            end

            else
            begin

                $display("Absolute Bias            : %f",

                         0.5 -
                         (entropy_ones * 1.0 /
                          read_count));

            end


            //--------------------------------------------------
            // Transition Probability
            //--------------------------------------------------

            $display("Transition 1 Probability : %f",

                     transition_ones * 1.0 /
                     read_count);


            //--------------------------------------------------
            // RTN Probability
            //--------------------------------------------------

            $display("Observed RTN Probability : %f",

                     rtn_flips * 1.0 /
                     read_count);

        end


        //--------------------------------------------------
        // Verification Checks
        //--------------------------------------------------

        $display("");

        $display("======================================================");

        $display(" Stochastic Verification Checks");

        $display("======================================================");


        //--------------------------------------------------
        // Required Samples
        //--------------------------------------------------

        if (read_count == NUM_READ_SAMPLES)
        begin

            $display("[PASS] Required read samples collected");

        end

        else
        begin

            $display("[FAIL] Required read samples not collected");

        end


        //--------------------------------------------------
        // Entropy 1 Check
        //--------------------------------------------------

        if (entropy_ones > 0)
        begin

            $display("[PASS] Entropy '1' samples observed");

        end

        else
        begin

            $display("[FAIL] No entropy '1' samples observed");

        end


        //--------------------------------------------------
        // Entropy 0 Check
        //--------------------------------------------------

        if (entropy_zeros > 0)
        begin

            $display("[PASS] Entropy '0' samples observed");

        end

        else
        begin

            $display("[FAIL] No entropy '0' samples observed");

        end


        //--------------------------------------------------
        // HRS -> LRS Check
        //--------------------------------------------------

        if (set_transitions > 0)
        begin

            $display("[PASS] HRS -> LRS transitions observed");

        end

        else
        begin

            $display("[FAIL] No HRS -> LRS transitions observed");

        end


        //--------------------------------------------------
        // LRS -> HRS Check
        //--------------------------------------------------

        if (reset_transitions > 0)
        begin

            $display("[PASS] LRS -> HRS transitions observed");

        end

        else
        begin

            $display("[FAIL] No LRS -> HRS transitions observed");

        end


        //--------------------------------------------------
        // Transition Bit Check
        //--------------------------------------------------

        if ((transition_ones > 0) &&
            (transition_zeros > 0))
        begin

            $display("[PASS] Both transition-bit values observed");

        end

        else
        begin

            $display("[FAIL] Transition bit is not varying");

        end


        //--------------------------------------------------
        // RTN Check
        //--------------------------------------------------

        if (rtn_flips > 0)
        begin

            $display("[PASS] RTN flip events observed");

        end

        else
        begin

            $display("[FAIL] No RTN flip events observed");

        end


        //--------------------------------------------------
        // Entropy Equation Check
        //--------------------------------------------------

        if (entropy_mismatch == 0)
        begin

            $display("[PASS] Entropy XOR logic verified");

        end

        else
        begin

            $display("[FAIL] Entropy XOR logic mismatch detected");

        end


        //--------------------------------------------------
        // Bitstream File Check
        //--------------------------------------------------

        if (read_count == NUM_READ_SAMPLES)
        begin

            $display("[PASS] Entropy bitstream contains %0d samples",
                     NUM_READ_SAMPLES);

        end

        else
        begin

            $display("[FAIL] Entropy bitstream sample count incorrect");

        end


        //--------------------------------------------------
        // Final Result
        //--------------------------------------------------

        if ((read_count == NUM_READ_SAMPLES) &&
            (entropy_ones > 0) &&
            (entropy_zeros > 0) &&
            (set_transitions > 0) &&
            (reset_transitions > 0) &&
            (transition_ones > 0) &&
            (transition_zeros > 0) &&
            (rtn_flips > 0) &&
            (entropy_mismatch == 0))
        begin

            $display("");

            $display("RESULT : STOCHASTIC ACTIVITY VERIFIED");

        end

        else
        begin

            $display("");

            $display("RESULT : STOCHASTIC VERIFICATION FAILED");

        end


        //--------------------------------------------------
        // End
        //--------------------------------------------------

        $display("======================================================");

        $finish;

    end

endmodule