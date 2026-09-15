`timescale 1ns / 1ps

// Low-utilization RO combiner.
// The 50 asynchronous RO outputs are sampled by a 2-flop synchronizer
// per RO, then XOR-reduced to one synchronous-domain entropy bit.
//
// The XOR itself is not a proof of entropy; statistical characterization
// and hardware validation are still required.

module ro_combiner (
    input  wire        clk,
    input  wire        rst,
    input  wire [49:0] ro_bits_async,
    output reg         entropy_bit
);

    (* ASYNC_REG = "TRUE" *) reg [49:0] meta_ff;
    (* ASYNC_REG = "TRUE" *) reg [49:0] sync_ff;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            meta_ff <= 50'b0;
            sync_ff <= 50'b0;
        end else begin
            meta_ff <= ro_bits_async;
            sync_ff <= meta_ff;
        end
    end

    always @(posedge clk or posedge rst) begin
        if (rst)
            entropy_bit <= 1'b0;
        else
            entropy_bit <= ^sync_ff;
    end

endmodule
