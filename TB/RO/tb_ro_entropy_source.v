`timescale 1ns / 1ps

module tb_ro_entropy_source;

    reg clk;
    reg rst;
    reg enable;
    wire entropy_bit;

    integer sample_count;
    integer ones;
    integer zeros;
    integer transitions;
    reg previous_bit;

    ro_entropy_source dut (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .entropy_bit(entropy_bit)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        sample_count = 0;
        ones = 0;
        zeros = 0;
        transitions = 0;
        previous_bit = 1'b0;

        rst = 1'b1;
        enable = 1'b0;

        #50;
        rst = 1'b0;

        // Allow the oscillators to start before sampling.
        #100;
        enable = 1'b1;

        repeat (10000) begin
            @(posedge clk);
            sample_count = sample_count + 1;

            if (entropy_bit)
                ones = ones + 1;
            else
                zeros = zeros + 1;

            if (sample_count > 1 && entropy_bit != previous_bit)
                transitions = transitions + 1;

            previous_bit = entropy_bit;
        end

        $display("==============================================");
        $display("50-RO ENTROPY SOURCE TEST");
        $display("Samples      = %0d", sample_count);
        $display("Ones         = %0d", ones);
        $display("Zeros        = %0d", zeros);
        $display("Transitions  = %0d", transitions);
        $display("==============================================");

        if (sample_count != 10000)
            $display("[FAIL] Incorrect sample count");
        else
            $display("[PASS] Sample collection completed");

        $finish;
    end

endmodule
