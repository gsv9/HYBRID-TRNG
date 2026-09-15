`timescale 1ns / 1ps

// AES-128 CBC-MAC style conditioner.
// On each input block: mac_next = AES_128(entropy_block XOR mac_state, AES_KEY).

module aes_cbc_mac_conditioner #(
    parameter [127:0] AES_KEY = 128'h000102030405060708090a0b0c0d0e0f
)(
    input  wire         clk,
    input  wire         rst,
    input  wire         block_valid,
    input  wire [127:0] entropy_block,
    output reg  [127:0] conditioned_block,
    output reg          conditioned_valid
);

    reg [127:0] mac_state;
    wire [127:0] aes_plaintext;
    wire [127:0] aes_ciphertext;
    wire aes_done;

    assign aes_plaintext = entropy_block ^ mac_state;

    aes128_encrypt u_aes (
        .clk(clk),
        .rst(rst),
        .start(block_valid),
        .plaintext(aes_plaintext),
        .key(AES_KEY),
        .ciphertext(aes_ciphertext),
        .done(aes_done)
    );

    always @(posedge clk) begin
        if (rst) begin
            mac_state         <= 128'b0;
            conditioned_block <= 128'b0;
            conditioned_valid <= 1'b0;
        end
        else begin
            conditioned_valid <= 1'b0;
            if (aes_done) begin
                mac_state         <= aes_ciphertext;
                conditioned_block <= aes_ciphertext;
                conditioned_valid <= 1'b1;
            end
        end
    end
endmodule
