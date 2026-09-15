`timescale 1ns / 1ps

module tb_entropy_accumulator_128;

    reg clk;
    reg rst;
    reg bit_valid;
    reg entropy_bit;

    wire [127:0] raw_entropy;
    wire raw_valid;

    integer i;
    integer block_count;

    entropy_accumulator_128 dut (
        .clk(clk),
        .rst(rst),
        .bit_valid(bit_valid),
        .entropy_bit(entropy_bit),
        .raw_entropy(raw_entropy),
        .raw_valid(raw_valid)
    );

    // 10 ns clock
    always #5 clk = ~clk;

    initial begin

        clk = 0;
        rst = 1;
        bit_valid = 0;
        entropy_bit = 0;
        block_count = 0;

        #20;

        rst = 0;

        // ------------------------------------------------
        // Send 256 valid entropy bits
        // Expected: two complete 128-bit blocks
        // ------------------------------------------------

        for (i = 0; i < 256; i = i + 1) begin

            @(negedge clk);

            bit_valid = 1'b1;

            // Deterministic test pattern
            // 10101010...
            entropy_bit = i % 2;

        end

        @(negedge clk);
        bit_valid = 0;

        #30;

        $display("==============================================");
        $display("       128-BIT ENTROPY ACCUMULATOR TB");
        $display("==============================================");
        $display("Expected blocks = 2");
        $display("Actual blocks   = %0d", block_count);

        if (block_count == 2)
            $display("[PASS] Two 128-bit blocks generated.");
        else
            $display("[FAIL] Incorrect number of blocks.");

        $display("==============================================");

        $finish;
    end

    // Monitor completed blocks
    always @(posedge clk) begin

        if (raw_valid) begin

            block_count = block_count + 1;

            $display("");
            $display("128-bit block %0d:", block_count);
            $display("%h", raw_entropy);

        end

    end

endmodule