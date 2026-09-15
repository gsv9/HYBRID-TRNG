`timescale 1ns / 1ps

// -----------------------------------------------------------------------------
// Low-power FPGA-facing TRNG top
//
// This wrapper keeps the wide 128-bit raw entropy block and debug signals
// internal. Only a compact 16-bit random output and a valid pulse are exposed
// at the FPGA boundary to reduce I/O utilization and estimated I/O power.
//
// The RO bank is fixed by BANK_SEL so only one RO bank is enabled at a time.
// The RRAM RTN model is driven by internal LFSR stimulus because the Arty A7
// does not contain physical RRAM.
// -----------------------------------------------------------------------------

module rram_ro_trng_low_power_top #(
    parameter integer RRAM_WIDTH = 8,
    parameter [2:0]   BANK_SEL   = 3'd0
)(
    input  wire        clk,
    input  wire        rst,
    input  wire        enable,

    output reg  [15:0] random_out,
    output reg         random_valid
);

    reg [RRAM_WIDTH-1:0] lfsr_set;
    reg [RRAM_WIDTH-1:0] lfsr_reset;
    reg [RRAM_WIDTH-1:0] lfsr_noise;
    reg [RRAM_WIDTH-1:0] lfsr_variation;

    wire rram_entropy;
    wire ro_entropy;
    wire hybrid_entropy;
    wire sample_valid;
    wire rram_state;
    wire [127:0] raw_entropy;
    wire raw_valid;

    function [7:0] next_lfsr;
        input [7:0] current;
        begin
            next_lfsr = {
                current[6:0],
                current[7] ^ current[5] ^ current[4] ^ current[3]
            };
        end
    endfunction

    always @(posedge clk) begin
        if (rst) begin
            lfsr_set       <= 8'hA5;
            lfsr_reset     <= 8'h3C;
            lfsr_noise     <= 8'h96;
            lfsr_variation <= 8'h5A;
        end
        else if (enable) begin
            lfsr_set       <= next_lfsr(lfsr_set);
            lfsr_reset     <= next_lfsr(lfsr_reset);
            lfsr_noise     <= next_lfsr(lfsr_noise);
            lfsr_variation <= next_lfsr(lfsr_variation);
        end
    end

    rram_ro_hybrid_accumulator #(
        .RRAM_WIDTH(RRAM_WIDTH),
        .RRAM_SET_THRESHOLD(8'd145),
        .RRAM_RESET_THRESHOLD(8'd110),
        .RRAM_NOISE_THRESHOLD(8'd96)
    ) u_trng_core (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .bank_sel(BANK_SEL),
        .rand_set(lfsr_set),
        .rand_reset(lfsr_reset),
        .rand_noise(lfsr_noise),
        .rand_variation(lfsr_variation),
        .rram_entropy(rram_entropy),
        .ro_entropy(ro_entropy),
        .hybrid_entropy(hybrid_entropy),
        .sample_valid(sample_valid),
        .rram_state(rram_state),
        .raw_entropy(raw_entropy),
        .raw_valid(raw_valid)
    );

    always @(posedge clk) begin
        if (rst) begin
            random_out   <= 16'h0000;
            random_valid <= 1'b0;
        end
        else begin
            random_valid <= 1'b0;

            if (raw_valid) begin
                random_out   <= raw_entropy[15:0];
                random_valid <= 1'b1;
            end
        end
    end

endmodule
