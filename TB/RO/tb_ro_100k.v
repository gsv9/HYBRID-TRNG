`timescale 1ns / 1ps

module tb_ro_100k;

    // ------------------------------------------------------------
    // Parameters
    // ------------------------------------------------------------
    localparam integer NUM_SAMPLES = 100000;

    // ------------------------------------------------------------
    // Signals
    // ------------------------------------------------------------
    reg clk;
    reg rst;
    reg enable;

    wire entropy_bit;

    // ------------------------------------------------------------
    // Counters
    // ------------------------------------------------------------
    integer sample_count;
    integer ones_count;
    integer zeros_count;
    integer transition_count;

    reg previous_bit;

    // File handle
    integer file_handle;

    // ------------------------------------------------------------
    // DUT
    // ------------------------------------------------------------
    ro_entropy_source dut (
        .clk         (clk),
        .rst         (rst),
        .enable      (enable),
        .entropy_bit (entropy_bit)
    );

    // ------------------------------------------------------------
    // 100 MHz clock
    // ------------------------------------------------------------
    always #5 clk = ~clk;

    // ------------------------------------------------------------
    // Main test
    // ------------------------------------------------------------
    initial begin

        // Initial values
        clk             = 1'b0;
        rst             = 1'b1;
        enable          = 1'b0;

        sample_count    = 0;
        ones_count      = 0;
        zeros_count     = 0;
        transition_count = 0;
        previous_bit    = 1'b0;

        // --------------------------------------------------------
        // Open output file
        // --------------------------------------------------------
        file_handle = $fopen("ro_entropy_100k.txt", "w");

        if (file_handle == 0) begin
            $display("[ERROR] Could not open ro_entropy_100k.txt");
            $finish;
        end

        $display("==============================================");
        $display("      50-RO 100,000-BIT ENTROPY TEST");
        $display("==============================================");

        // --------------------------------------------------------
        // Reset
        // --------------------------------------------------------
        #20;

        rst = 1'b0;

        // Enable RO array
        enable = 1'b1;

        $display("RO array enabled.");
        $display("Waiting for synchronization...");
        
        // --------------------------------------------------------
        // Synchronizer warm-up
        // Two flip-flops + extra settling cycles
        // --------------------------------------------------------
        repeat (10)
            @(negedge clk);

        $display("Synchronization complete.");
        $display("Starting entropy collection...");

        // --------------------------------------------------------
        // Collect 100,000 entropy bits
        // --------------------------------------------------------
        while (sample_count < NUM_SAMPLES) begin

            @(negedge clk);

            // Write bit to file
            $fwrite(file_handle, "%1b", entropy_bit);

            // Count ones and zeros
            if (entropy_bit == 1'b1)
                ones_count = ones_count + 1;
            else
                zeros_count = zeros_count + 1;

            // Count transitions
            if (sample_count > 0) begin
                if (entropy_bit != previous_bit)
                    transition_count = transition_count + 1;
            end

            previous_bit = entropy_bit;

            sample_count = sample_count + 1;

            // Progress message
            if ((sample_count % 10000) == 0) begin
                $display(
                    "Collected %0d / %0d bits",
                    sample_count,
                    NUM_SAMPLES
                );
            end
        end

        // --------------------------------------------------------
        // Close file
        // --------------------------------------------------------
        $fclose(file_handle);

        // --------------------------------------------------------
        // Display results
        // --------------------------------------------------------
        $display("");
        $display("==============================================");
        $display("        COLLECTION COMPLETE");
        $display("==============================================");

        $display("Samples      = %0d", sample_count);
        $display("Ones         = %0d", ones_count);
        $display("Zeros        = %0d", zeros_count);
        $display("Transitions  = %0d", transition_count);

        $display("");
        $display("Output file: ro_entropy_100k.txt");

        // --------------------------------------------------------
        // Basic verification
        // --------------------------------------------------------
        if (sample_count == NUM_SAMPLES) begin
            $display("[PASS] 100,000 entropy samples collected.");
        end
        else begin
            $display("[FAIL] Incorrect number of samples.");
        end

        $display("==============================================");

        $finish;
    end

endmodule