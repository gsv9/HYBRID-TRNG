`timescale 1ns / 1ps

// -----------------------------------------------------------------------------
// RRAM + Banked RO Hybrid + 128-bit Entropy Accumulator
//
// Existing rram_ro_hybrid block is kept unchanged.
//
// Data flow:
//
//     RRAM entropy ──┐
//                    ├── XOR ──> hybrid_entropy
//     RO entropy ────┘
//                           │
//                      sample_valid
//                           │
//                           ▼
//                   128-bit accumulator
//                           │
//                           ▼
//                    raw_entropy[127:0]
//                           │
//                           ▼
//                        raw_valid
// -----------------------------------------------------------------------------

module rram_ro_hybrid_accumulator #(
    parameter integer RRAM_WIDTH = 8,
    parameter integer RRAM_SET_THRESHOLD   = 8'd145,
    parameter integer RRAM_RESET_THRESHOLD = 8'd110,
    parameter integer RRAM_NOISE_THRESHOLD = 8'd96
)(
    input wire clk,
    input wire rst,
    input wire enable,

    // RO bank selection
    input wire [2:0] bank_sel,

    // RRAM stochastic stimulus
    input wire [RRAM_WIDTH-1:0] rand_set,
    input wire [RRAM_WIDTH-1:0] rand_reset,
    input wire [RRAM_WIDTH-1:0] rand_noise,
    input wire [RRAM_WIDTH-1:0] rand_variation,

    // Raw entropy outputs for observation/debug
    output wire rram_entropy,
    output wire ro_entropy,
    output wire hybrid_entropy,

    // RRAM sampling event
    output wire sample_valid,

    // RRAM state
    output wire rram_state,

    // 128-bit accumulated entropy block
    output wire [127:0] raw_entropy,

    // One-clock pulse after 128 valid samples
    output wire raw_valid
);

    // -------------------------------------------------------------------------
    // Existing RRAM + RO hybrid
    // -------------------------------------------------------------------------

    rram_ro_hybrid #(
        .RRAM_WIDTH(RRAM_WIDTH),
        .RRAM_SET_THRESHOLD(RRAM_SET_THRESHOLD),
        .RRAM_RESET_THRESHOLD(RRAM_RESET_THRESHOLD),
        .RRAM_NOISE_THRESHOLD(RRAM_NOISE_THRESHOLD)
    ) u_hybrid (
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

    // -------------------------------------------------------------------------
    // 128-bit entropy accumulator
    // -------------------------------------------------------------------------

    entropy_accumulator_128 u_accumulator (
        .clk(clk),
        .rst(rst),

        // Collect only when the hybrid sample is valid
        .bit_valid(sample_valid),
        .entropy_bit(hybrid_entropy),

        .raw_entropy(raw_entropy),
        .raw_valid(raw_valid)
    );

endmodule