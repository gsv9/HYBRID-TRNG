`timescale 1ns / 1ps

module rram_ro_trng_aes_uart_top #(
    parameter integer CLK_FREQ_HZ = 100_000_000,
    parameter integer BAUD_RATE   = 115200,
    parameter integer RRAM_WIDTH  = 8,
    parameter [2:0]   BANK_SEL    = 3'd0,
    parameter [127:0] AES_KEY     = 128'h000102030405060708090a0b0c0d0e0f
)(
    input  wire clk,
    input  wire rst,
    input  wire enable,
    output wire uart_tx,
    output reg  block_valid
);

    localparam [1:0] TX_IDLE = 2'd0;
    localparam [1:0] TX_LOAD = 2'd1;
    localparam [1:0] TX_WAIT = 2'd2;

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
    wire [127:0] conditioned_entropy;
    wire conditioned_valid;

    reg [127:0] tx_block;
    reg [3:0] byte_index;
    reg [1:0] tx_state;
    reg uart_start;
    reg [7:0] uart_data;
    wire uart_busy;
    wire uart_done;

    function [7:0] next_lfsr;
        input [7:0] current;
        begin
            next_lfsr = {current[6:0], current[7] ^ current[5] ^ current[4] ^ current[3]};
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

    aes_cbc_mac_conditioner #(
        .AES_KEY(AES_KEY)
    ) u_conditioner (
        .clk(clk),
        .rst(rst),
        .block_valid(raw_valid),
        .entropy_block(raw_entropy),
        .conditioned_block(conditioned_entropy),
        .conditioned_valid(conditioned_valid)
    );

    uart_tx #(
        .CLK_FREQ_HZ(CLK_FREQ_HZ),
        .BAUD_RATE(BAUD_RATE)
    ) u_uart_tx (
        .clk(clk),
        .rst(rst),
        .tx_start(uart_start),
        .tx_data(uart_data),
        .tx(uart_tx),
        .tx_busy(uart_busy),
        .tx_done(uart_done)
    );

    always @(posedge clk) begin
        if (rst) begin
            tx_block    <= 128'b0;
            byte_index  <= 4'd0;
            tx_state    <= TX_IDLE;
            uart_start  <= 1'b0;
            uart_data   <= 8'h00;
            block_valid <= 1'b0;
        end
        else begin
            uart_start  <= 1'b0;
            block_valid <= 1'b0;

            case (tx_state)
                TX_IDLE: begin
                    if (conditioned_valid) begin
                        tx_block    <= conditioned_entropy;
                        byte_index  <= 4'd0;
                        block_valid <= 1'b1;
                        tx_state    <= TX_LOAD;
                    end
                end

                TX_LOAD: begin
                    if (!uart_busy) begin
                        uart_data  <= tx_block[127:120];
                        tx_block   <= {tx_block[119:0], 8'h00};
                        uart_start <= 1'b1;
                        tx_state   <= TX_WAIT;
                    end
                end

                TX_WAIT: begin
                    if (uart_done) begin
                        if (byte_index == 4'd15) begin
                            byte_index <= 4'd0;
                            tx_state   <= TX_IDLE;
                        end
                        else begin
                            byte_index <= byte_index + 1'b1;
                            tx_state   <= TX_LOAD;
                        end
                    end
                end

                default: tx_state <= TX_IDLE;
            endcase
        end
    end
endmodule
