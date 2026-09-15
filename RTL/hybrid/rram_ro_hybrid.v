`timescale 1ns / 1ps

// -----------------------------------------------------------------------------
// RRAM + Banked RO Hybrid Entropy Source
//
// Combines one RRAM entropy sample and one synchronized RO entropy sample
// using XOR:
//
//     hybrid_entropy = rram_entropy ^ ro_entropy
//
// Existing RRAM and RO blocks are kept unchanged.
//
// sample_valid is asserted during the RRAM READ state and can be used by
// the testbench as the common sampling event.
// -----------------------------------------------------------------------------

module rram_ro_hybrid #(
    parameter integer RRAM_WIDTH = 8,
    parameter integer RRAM_SET_THRESHOLD   = 8'd145,
    parameter integer RRAM_RESET_THRESHOLD = 8'd110,
    parameter integer RRAM_NOISE_THRESHOLD = 8'd96
)(
    input  wire       clk,
    input  wire       rst,
    input  wire       enable,

    // Banked RO selection: 0,1,2,3,4.
    // For the first hybrid experiment use bank 0 (10 active ROs).
    input  wire [2:0] bank_sel,

    // RRAM stochastic stimulus
    input  wire [RRAM_WIDTH-1:0] rand_set,
    input  wire [RRAM_WIDTH-1:0] rand_reset,
    input  wire [RRAM_WIDTH-1:0] rand_noise,
    input  wire [RRAM_WIDTH-1:0] rand_variation,

    output wire       rram_entropy,
    output wire       ro_entropy,
    output wire       hybrid_entropy,
    output wire       sample_valid,
    output wire       rram_state
);

    wire rram_do_read;

    // -------------------------------------------------------------------------
    // RRAM entropy source
    // -------------------------------------------------------------------------
    rram_cell #(
        .WIDTH(RRAM_WIDTH),
        .INIT_SET_THRESHOLD(RRAM_SET_THRESHOLD),
        .INIT_RESET_THRESHOLD(RRAM_RESET_THRESHOLD),
        .INIT_NOISE_THRESHOLD(RRAM_NOISE_THRESHOLD)
    ) u_rram (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .rand_set(rand_set),
        .rand_reset(rand_reset),
        .rand_noise(rand_noise),
        .rand_variation(rand_variation),
        .entropy_bit(rram_entropy),
        .rram_state(rram_state)
    );

    // Use the RRAM FSM's READ indication as the common sampling event.
    assign rram_do_read = u_rram.do_read;

    // -------------------------------------------------------------------------
    // Banked RO entropy source
    // -------------------------------------------------------------------------
    ro_entropy_source_banked #(
        .NUM_BANKS(5)
    ) u_ro (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .bank_sel(bank_sel),
        .entropy_bit(ro_entropy)
    );

    // -------------------------------------------------------------------------
    // Hybrid combiner
    // -------------------------------------------------------------------------
    assign hybrid_entropy = rram_entropy ^ ro_entropy;

    // One hybrid sample is considered valid during each RRAM READ state.
    assign sample_valid = rram_do_read;

endmodule
