`timescale 1ns / 1ps

module tb_rram_ro_hybrid_accumulator;

    // ====================================================
    // Parameters
    // ====================================================
    localparam integer RRAM_WIDTH = 8;

    // ====================================================
    // Clock / reset / enable
    // ====================================================
    reg clk;
    reg rst;
    reg enable;

    // ====================================================
    // RO bank selection
    // ====================================================
    reg [2:0] bank_sel;

    // ====================================================
    // RRAM stochastic stimulus
    // ====================================================
    reg [RRAM_WIDTH-1:0] rand_set;
    reg [RRAM_WIDTH-1:0] rand_reset;
    reg [RRAM_WIDTH-1:0] rand_noise;
    reg [RRAM_WIDTH-1:0] rand_variation;

    // ====================================================
    // DUT outputs
    // ====================================================
    wire rram_entropy;
    wire ro_entropy;
    wire hybrid_entropy;
    wire sample_valid;
    wire rram_state;

    wire [127:0] raw_entropy;
    wire raw_valid;

    // ====================================================
    // Counters
    // ====================================================
    integer sample_count;
    integer block_count;

    // ====================================================
    // LFSR registers
    // Deterministic pseudo-random stimulus for simulation
    // only. This is NOT physical randomness.
    // ====================================================
    reg [7:0] lfsr_set;
    reg [7:0] lfsr_reset;
    reg [7:0] lfsr_noise;
    reg [7:0] lfsr_variation;

    // ====================================================
    // DUT
    // ====================================================
    rram_ro_hybrid_accumulator #(
        .RRAM_WIDTH(RRAM_WIDTH),
        .RRAM_SET_THRESHOLD(8'd145),
        .RRAM_RESET_THRESHOLD(8'd110),
        .RRAM_NOISE_THRESHOLD(8'd96)
    ) dut (

        .clk(clk),
        .rst(rst),
        .enable(enable),

        .bank_sel(bank_sel),

        .rand_set(rand_set),
        .rand_reset(rand_reset),
        .rand_noise(rand_noise),
        .rand_variation(rand_variation),

        .rram_entropy(rram_entropy),
        .ro_entropy(ro_entropy),
        .hybrid_entropy(hybrid_entropy),

        .sample_valid(sample_valid),

        .rram_state(rram_state),

        .raw_entropy(raw_entropy),
        .raw_valid(raw_valid)
    );

    // ====================================================
    // 10 ns clock
    // ====================================================
    always #5 clk = ~clk;


    // ====================================================
    // LFSR function
    // ====================================================
    function [7:0] next_lfsr;
        input [7:0] current;

        begin
            next_lfsr = {
                current[6:0],
                current[7] ^
                current[5] ^
                current[4] ^
                current[3]
            };
        end
    endfunction


    // ====================================================
    // Initial setup
    // ====================================================
    initial begin

        // ------------------------------------------------
        // Initial values
        // ------------------------------------------------
        clk = 1'b0;
        rst = 1'b1;
        enable = 1'b0;

        // Bank 0 = 10 active ROs
        bank_sel = 3'd0;

        // ------------------------------------------------
        // RRAM LFSR seeds
        // ------------------------------------------------
        lfsr_set       = 8'hA5;
        lfsr_reset     = 8'h3C;
        lfsr_noise     = 8'h96;
        lfsr_variation = 8'h5A;

        rand_set       = 8'hA5;
        rand_reset     = 8'h3C;
        rand_noise     = 8'h96;
        rand_variation = 8'h5A;

        // ------------------------------------------------
        // Counters
        // ------------------------------------------------
        sample_count = 0;
        block_count  = 0;

        // ------------------------------------------------
        // Reset
        // ------------------------------------------------
        #20;

        rst = 1'b0;
        enable = 1'b1;

        $display("");
        $display("======================================================");
        $display(" RRAM + BANKED RO + 128-BIT ACCUMULATOR TEST");
        $display("======================================================");
        $display("RO Bank               = %0d", bank_sel);
        $display("Target valid samples  = 256");
        $display("Expected 128-bit blocks = 2");
        $display("======================================================");
        $display("");

    end


    // ====================================================
    // Update RRAM stimulus on negative clock edge
    // ====================================================
    always @(negedge clk) begin

        if (rst) begin

            lfsr_set       <= 8'hA5;
            lfsr_reset     <= 8'h3C;
            lfsr_noise     <= 8'h96;
            lfsr_variation <= 8'h5A;

            rand_set       <= 8'hA5;
            rand_reset     <= 8'h3C;
            rand_noise     <= 8'h96;
            rand_variation <= 8'h5A;

        end

        else if (enable) begin

            // Update LFSRs
            lfsr_set       <= next_lfsr(lfsr_set);
            lfsr_reset     <= next_lfsr(lfsr_reset);
            lfsr_noise     <= next_lfsr(lfsr_noise);
            lfsr_variation <= next_lfsr(lfsr_variation);

            // Apply next values to RRAM
            rand_set       <= next_lfsr(lfsr_set);
            rand_reset     <= next_lfsr(lfsr_reset);
            rand_noise     <= next_lfsr(lfsr_noise);
            rand_variation <= next_lfsr(lfsr_variation);

        end

    end


    // ====================================================
    // Count valid hybrid samples
    // ====================================================
    always @(posedge clk) begin

        if (rst) begin

            sample_count <= 0;

        end

        else begin

            if (sample_valid) begin

                sample_count <= sample_count + 1;

                $display(
                    "Sample %0d : RRAM=%b  RO=%b  HYBRID=%b",
                    sample_count + 1,
                    rram_entropy,
                    ro_entropy,
                    hybrid_entropy
                );

            end

        end

    end


    // ====================================================
    // Monitor completed 128-bit blocks
    // ====================================================
    always @(posedge clk) begin

        if (raw_valid) begin

            block_count <= block_count + 1;

            $display("");
            $display("----------------------------------------------");
            $display("128-BIT RAW ENTROPY BLOCK %0d", block_count + 1);
            $display("----------------------------------------------");
            $display("%h", raw_entropy);
            $display("----------------------------------------------");
            $display("");

        end

    end


    // ====================================================
    // Test completion
    //
    // IMPORTANT:
    // Wait for BOTH:
    //   256 valid samples
    //   2 completed 128-bit blocks
    //
    // This avoids the previous race where the simulation
    // terminated immediately after sample 256 before the
    // second raw_valid event was counted.
    // ====================================================
    always @(posedge clk) begin

        if ((sample_count >= 256) &&
            (block_count >= 2)) begin

            #10;

            $display("");
            $display("======================================================");
            $display("              TEST COMPLETE");
            $display("======================================================");
            $display("Valid hybrid samples = %0d", sample_count);
            $display("128-bit blocks        = %0d", block_count);
            $display("");

            // ------------------------------------------------
            // Sample count check
            // ------------------------------------------------
            if (sample_count == 256)
                $display("[PASS] 256 valid hybrid samples collected.");
            else
                $display(
                    "[FAIL] Expected 256 samples, got %0d.",
                    sample_count
                );

            // ------------------------------------------------
            // Block count check
            // ------------------------------------------------
            if (block_count == 2)
                $display(
                    "[PASS] Two 128-bit raw entropy blocks generated."
                );
            else
                $display(
                    "[FAIL] Expected 2 blocks, got %0d.",
                    block_count
                );

            // ------------------------------------------------
            // Final result
            // ------------------------------------------------
            if ((sample_count == 256) &&
                (block_count == 2)) begin

                $display("");
                $display("[PASS] RRAM + RO + 128-bit accumulator integration verified.");

            end
            else begin

                $display("");
                $display("[FAIL] Integration test failed.");

            end

            $display("======================================================");

            $finish;

        end

    end


    // ====================================================
    // Safety timeout
    //
    // Prevents simulation from running forever if the
    // expected number of valid samples is never reached.
    // ====================================================
    initial begin

        #100000;

        $display("");
        $display("======================================================");
        $display("[TIMEOUT] Simulation exceeded expected time.");
        $display("Samples = %0d", sample_count);
        $display("Blocks  = %0d", block_count);
        $display("======================================================");

        $finish;

    end

endmodule