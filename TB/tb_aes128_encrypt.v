`timescale 1ns / 1ps

module tb_aes128_encrypt;
    reg clk;
    reg rst;
    reg start;
    reg [127:0] plaintext;
    reg [127:0] key;
    wire [127:0] ciphertext;
    wire done;

    aes128_encrypt dut (
        .clk(clk),
        .rst(rst),
        .start(start),
        .plaintext(plaintext),
        .key(key),
        .ciphertext(ciphertext),
        .done(done)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        rst = 1'b1;
        start = 1'b0;
        plaintext = 128'h00112233445566778899aabbccddeeff;
        key       = 128'h000102030405060708090a0b0c0d0e0f;

        #20;
        rst = 1'b0;
        @(negedge clk);
        start = 1'b1;
        @(negedge clk);
        start = 1'b0;

        wait(done == 1'b1);
        #1;

        $display("AES ciphertext = %h", ciphertext);
        if (ciphertext == 128'h69c4e0d86a7b0430d8cdb78070b4c55a)
            $display("[PASS] AES-128 known-answer test passed.");
        else
            $display("[FAIL] AES-128 known-answer test failed.");

        #20;
        $finish;
    end
endmodule
