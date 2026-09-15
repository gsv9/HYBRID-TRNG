`timescale 1ns / 1ps

// -----------------------------------------------------------------------------
// 100,000-bit RRAM + RO XOR Hybrid Testbench
//
// First experiment:
//     bank_sel = 3'd0  -> Bank 0 active (10 ROs)
//     RRAM threshold = 96 for RTN, matching the previous RRAM stochastic test.
//
// The RRAM LFSR stimulus method is intentionally the same as the existing
// tb_rram_cell_stochastic.v methodology.
//
// The RRAM READ event is used as the common sampling event. At each valid
// sample, the testbench records:
//
//     RRAM entropy
//     RO entropy
//     Hybrid = RRAM XOR RO
//
// Output files:
//     rram_ro_hybrid_100k.txt
//     rram_ro_hybrid_rram_100k.txt
//     rram_ro_hybrid_ro_100k.txt
// -----------------------------------------------------------------------------

module tb_rram_ro_hybrid_100k;

    parameter integer WIDTH = 8;
    parameter integer NUM_READ_SAMPLES = 100000;
    parameter integer MAX_CYCLES = 500000;

    parameter [7:0] INIT_SET_THRESHOLD   = 8'd145;
    parameter [7:0] INIT_RESET_THRESHOLD = 8'd110;
    parameter [7:0] INIT_NOISE_THRESHOLD = 8'd96;

    reg clk;
    reg rst;
    reg enable;

    // Select exactly one RO bank.
    // Bank 0 = 10 ROs.
    reg [2:0] bank_sel;

    reg [WIDTH-1:0] rand_set;
    reg [WIDTH-1:0] rand_reset;
    reg [WIDTH-1:0] rand_noise;
    reg [WIDTH-1:0] rand_variation;

    wire rram_entropy;
    wire ro_entropy;
    wire hybrid_entropy;
    wire sample_valid;
    wire rram_state;

    reg [7:0] lfsr_set;
    reg [7:0] lfsr_reset;
    reg [7:0] lfsr_noise;
    reg [7:0] lfsr_variation;

    integer sample_count;
    integer total_cycles;

    integer rram_ones;
    integer rram_zeros;
    integer ro_ones;
    integer ro_zeros;
    integer hybrid_ones;
    integer hybrid_zeros;

    integer rram_transitions;
    integer ro_transitions;
    integer hybrid_transitions;

    reg previous_rram_bit;
    reg previous_ro_bit;
    reg previous_hybrid_bit;

    integer run_seed;
    integer file_hybrid;
    integer file_rram;
    integer file_ro;

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

    // -------------------------------------------------------------------------
    // DUT
    // -------------------------------------------------------------------------
    rram_ro_hybrid #(
        .RRAM_WIDTH(WIDTH),
        .RRAM_SET_THRESHOLD(INIT_SET_THRESHOLD),
        .RRAM_RESET_THRESHOLD(INIT_RESET_THRESHOLD),
        .RRAM_NOISE_THRESHOLD(INIT_NOISE_THRESHOLD)
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
        .rram_state(rram_state)
    );

    // 100 MHz system clock
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // -------------------------------------------------------------------------
    // Sample and statistics collection
    //
    // #1 allows the DUT's nonblocking assignments to settle after the
    // positive edge before the sample is evaluated.
    // -------------------------------------------------------------------------
    always @(posedge clk)
    begin
        #1;

        if (!rst)
        begin
            total_cycles = total_cycles + 1;

            if (sample_valid && (sample_count < NUM_READ_SAMPLES))
            begin
                // RRAM stream
                if (rram_entropy == 1'b1)
                    rram_ones = rram_ones + 1;
                else
                    rram_zeros = rram_zeros + 1;

                if (sample_count > 0)
                    if (rram_entropy != previous_rram_bit)
                        rram_transitions = rram_transitions + 1;

                previous_rram_bit = rram_entropy;

                // RO stream
                if (ro_entropy == 1'b1)
                    ro_ones = ro_ones + 1;
                else
                    ro_zeros = ro_zeros + 1;

                if (sample_count > 0)
                    if (ro_entropy != previous_ro_bit)
                        ro_transitions = ro_transitions + 1;

                previous_ro_bit = ro_entropy;

                // Hybrid stream
                if (hybrid_entropy == 1'b1)
                    hybrid_ones = hybrid_ones + 1;
                else
                    hybrid_zeros = hybrid_zeros + 1;

                if (sample_count > 0)
                    if (hybrid_entropy != previous_hybrid_bit)
                        hybrid_transitions = hybrid_transitions + 1;

                previous_hybrid_bit = hybrid_entropy;

                // Write all three aligned streams.
                $fwrite(file_hybrid, "%1b", hybrid_entropy);
                $fwrite(file_rram,   "%1b", rram_entropy);
                $fwrite(file_ro,     "%1b", ro_entropy);

                sample_count = sample_count + 1;

                if ((sample_count % 10000) == 0)
                    $display("Collected %0d / %0d hybrid samples",
                             sample_count, NUM_READ_SAMPLES);
            end
        end
    end

    // -------------------------------------------------------------------------
    // Main test
    // -------------------------------------------------------------------------
    initial
    begin
        clk = 1'b0;
        rst = 1'b1;
        enable = 1'b0;

        // Bank 0 = exactly 10 ROs.
        bank_sel = 3'd0;

        rand_set = 8'd0;
        rand_reset = 8'd0;
        rand_noise = 8'd0;
        rand_variation = 8'd0;

        sample_count = 0;
        total_cycles = 0;

        rram_ones = 0;
        rram_zeros = 0;
        ro_ones = 0;
        ro_zeros = 0;
        hybrid_ones = 0;
        hybrid_zeros = 0;

        rram_transitions = 0;
        ro_transitions = 0;
        hybrid_transitions = 0;

        previous_rram_bit = 1'b0;
        previous_ro_bit = 1'b0;
        previous_hybrid_bit = 1'b0;

        run_seed = 37;

        // Same seed style as the existing RRAM stochastic TB.
        lfsr_set       = 8'hA5 ^ (run_seed + 8'h11);
        lfsr_reset     = 8'hC3 ^ (run_seed + 8'h27);
        lfsr_noise     = 8'hE7 ^ (run_seed + 8'h43);
        lfsr_variation = 8'h9B ^ (run_seed + 8'h65);

        if (lfsr_set == 8'd0)       lfsr_set = 8'hA5;
        if (lfsr_reset == 8'd0)     lfsr_reset = 8'hC3;
        if (lfsr_noise == 8'd0)     lfsr_noise = 8'hE7;
        if (lfsr_variation == 8'd0) lfsr_variation = 8'h9B;

        rand_set       = lfsr_set;
        rand_reset     = lfsr_reset;
        rand_noise     = lfsr_noise;
        rand_variation = lfsr_variation;

        file_hybrid = $fopen("rram_ro_hybrid_100k.txt", "w");
        file_rram   = $fopen("rram_ro_hybrid_rram_100k.txt", "w");
        file_ro     = $fopen("rram_ro_hybrid_ro_100k.txt", "w");

        if ((file_hybrid == 0) || (file_rram == 0) || (file_ro == 0))
        begin
            $display("[ERROR] Could not open one or more output files.");
            $finish;
        end

        $display("======================================================");
        $display("       RRAM + RO XOR HYBRID / 100,000-BIT TEST");
        $display("======================================================");
        $display("RO Bank      = %0d", bank_sel);
        $display("Active ROs   = 10");
        $display("RRAM RTN threshold = %0d", INIT_NOISE_THRESHOLD);
        $display("");

        // Initial reset.
        #20;
        rst = 1'b0;

        // Small gap, matching the existing RRAM testbench style.
        #10;

        enable = 1'b1;

        $display("RRAM and selected RO bank enabled.");
        $display("Waiting for synchronization / startup...");

        // Allow the RO synchronizer to settle.
        repeat (10)
            @(negedge clk);

        $display("Synchronization complete.");
        $display("Starting aligned hybrid collection...");
        $display("");

        // Wait until 100,000 READ events are collected.
        while ((sample_count < NUM_READ_SAMPLES) &&
               (total_cycles < MAX_CYCLES))
        begin
            @(posedge clk);
        end

        enable = 1'b0;

        $fclose(file_hybrid);
        $fclose(file_rram);
        $fclose(file_ro);

        $display("");
        $display("======================================================");
        $display("             HYBRID COLLECTION COMPLETE");
        $display("======================================================");
        $display("Samples          = %0d", sample_count);
        $display("Total cycles     = %0d", total_cycles);
        $display("");

        $display("RRAM:");
        $display("  Ones           = %0d", rram_ones);
        $display("  Zeros          = %0d", rram_zeros);
        $display("  Transitions    = %0d", rram_transitions);

        $display("");
        $display("RO:");
        $display("  Ones           = %0d", ro_ones);
        $display("  Zeros          = %0d", ro_zeros);
        $display("  Transitions    = %0d", ro_transitions);

        $display("");
        $display("HYBRID XOR:");
        $display("  Ones           = %0d", hybrid_ones);
        $display("  Zeros          = %0d", hybrid_zeros);
        $display("  Transitions    = %0d", hybrid_transitions);

        if (sample_count == NUM_READ_SAMPLES)
            $display("[PASS] 100,000 aligned hybrid samples collected.");
        else
            $display("[FAIL] Required hybrid samples were not collected.");

        $display("");
        $display("Output files:");
        $display("  rram_ro_hybrid_100k.txt");
        $display("  rram_ro_hybrid_rram_100k.txt");
        $display("  rram_ro_hybrid_ro_100k.txt");
        $display("======================================================");

        #100;
        $finish;
    end

    // -------------------------------------------------------------------------
    // Update LFSRs on the negative clock edge so new values are present before
    // the next positive DUT edge, matching the existing RRAM stochastic TB.
    // -------------------------------------------------------------------------
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
