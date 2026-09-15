`timescale 1ns / 1ps

module ro_entropy_source_banked #(
    parameter integer NUM_BANKS = 5
)(
    input  wire       clk,
    input  wire       rst,
    input  wire       enable,
    input  wire [2:0] bank_sel,
    output wire       entropy_bit
);

    wire [49:0] ro_bits;

    ro_array_banked ro_array (
        .enable  (enable),
        .bank_sel(bank_sel),
        .ro_bits (ro_bits)
    );

    ro_combiner #(.NUM_ROS(50)) ro_combiner (
        .clk         (clk),
        .rst         (rst),
        .ro_bits_async(ro_bits),
        .entropy_bit (entropy_bit)
    );

endmodule
