`timescale 1ns / 1ps

module top_tb;

    //------------------------------------------------------
    // DUT Inputs
    //------------------------------------------------------

    reg clk;
    reg rst;
    reg enable;

    //------------------------------------------------------
    // DUT Outputs
    //------------------------------------------------------

    wire [127:0] block_out;
    wire         block_ready;

    wire b_ro_probe;
    wire b_rram_probe;

    //------------------------------------------------------
    // Test Parameters
    //------------------------------------------------------

    parameter integer TARGET_BLOCKS = 1000;

    //------------------------------------------------------
    // Test Statistics
    //------------------------------------------------------

    integer block_num;

    integer total_bits;

    integer entropy_file;

    integer i;

    reg [127:0] captured_block;

    //------------------------------------------------------
    // DUT
    //------------------------------------------------------

    top #(
        .NUM_RO(8),
        .WIDTH(8)
    )
    dut (
        .clk(clk),
        .rst(rst),
        .enable(enable),

        .block_out(block_out),
        .block_ready(block_ready),

        .b_ro_probe(b_ro_probe),
        .b_rram_probe(b_rram_probe)
    );

    //------------------------------------------------------
    // Clock Generation
    //------------------------------------------------------

    initial
        clk = 1'b0;

    always #5 clk = ~clk;

    //------------------------------------------------------
    // Main Test Sequence
    //------------------------------------------------------

    initial
    begin

        //--------------------------------------------------
        // Initialize
        //--------------------------------------------------

        block_num  = 0;
        total_bits = 0;

        enable = 1'b0;
        rst    = 1'b1;

        //--------------------------------------------------
        // Open Output File
        //--------------------------------------------------

        entropy_file = $fopen("hybrid_entropy_bitstream.txt", "w");

        if (entropy_file == 0)
        begin

            $display("[ERROR] Could not open entropy output file.");

            $finish;

        end
        else
        begin

            $display("[INFO] Hybrid entropy output file opened.");

            $display("       hybrid_entropy_bitstream.txt");

        end

        //--------------------------------------------------
        // Reset
        //--------------------------------------------------

        #20;

        rst = 1'b0;

        //--------------------------------------------------
        // Enable Hybrid Generator
        //--------------------------------------------------

        #10;

        enable = 1'b1;

        $display("");
        $display("======================================================");
        $display(" HYBRID RO + RRAM BITSTREAM GENERATION");
        $display("======================================================");

        $display("Target Blocks : %0d", TARGET_BLOCKS);

        $display("Target Bits   : %0d", TARGET_BLOCKS * 128);

        $display("");

    end

    //------------------------------------------------------
    // Capture Every 128-bit Hybrid Block
    //------------------------------------------------------

    always @(posedge clk)
    begin

        if (block_ready && enable)
        begin

            //--------------------------------------------------
            // Count Block
            //--------------------------------------------------

            block_num = block_num + 1;

            //--------------------------------------------------
            // Capture Current Block
            //--------------------------------------------------

            captured_block = block_out;

            //--------------------------------------------------
            // Write 128 bits individually
            //--------------------------------------------------

            for (i = 127; i >= 0; i = i - 1)
            begin

                $fwrite(
                    entropy_file,
                    "%b\n",
                    captured_block[i]
                );

            end

            //--------------------------------------------------
            // Update Bit Count
            //--------------------------------------------------

            total_bits = total_bits + 128;

            //--------------------------------------------------
            // Display Progress
            //--------------------------------------------------

            if (
                (block_num <= 10) ||
                ((block_num % 100) == 0)
            )
            begin

                $display(
                    "[INFO] Block %0d captured | Total bits = %0d",
                    block_num,
                    total_bits
                );

            end

            //--------------------------------------------------
            // Stop After Required Blocks
            //--------------------------------------------------

            if (block_num >= TARGET_BLOCKS)
            begin

                enable = 1'b0;

                //--------------------------------------------------
                // Close File
                //--------------------------------------------------

                $fclose(entropy_file);

                $display("");

                $display("[INFO] Hybrid entropy bitstream complete.");

                $display("Total Blocks : %0d", block_num);

                $display("Total Bits   : %0d", total_bits);

                $display("");

                $display(
                    "[INFO] Output file:"
                );

                $display(
                    "       hybrid_entropy_bitstream.txt"
                );

                $display("");

                $display("======================================================");

                $finish;

            end

        end

    end

endmodule