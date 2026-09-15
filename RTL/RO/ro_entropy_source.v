`timescale 1ns / 1ps

// Top-level 50-RO entropy source.
// 17 x 3-stage + 17 x 5-stage + 16 x 7-stage = 50 ROs.

module ro_entropy_source (
    input  wire clk,
    input  wire rst,
    input  wire enable,
    output wire entropy_bit
);

    wire [49:0] ro_bits;

    ro_array u_ro_array (
        .enable(enable),
        .ro_bits(ro_bits)
    );

    ro_combiner u_ro_combiner (
        .clk(clk),
        .rst(rst),
        .ro_bits_async(ro_bits),
        .entropy_bit(entropy_bit)
    );

endmodule
