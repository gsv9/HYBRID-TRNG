`timescale 1ns / 1ps

module ro_combiner #(
    parameter integer NUM_ROS = 50
)(
    input  wire             clk,
    input  wire             rst,
    input  wire [NUM_ROS-1:0] ro_bits_async,
    output reg              entropy_bit
);

    (* ASYNC_REG = "TRUE" *) reg [NUM_ROS-1:0] meta_ff;
    (* ASYNC_REG = "TRUE" *) reg [NUM_ROS-1:0] sync_ff;

    always @(posedge clk) begin
        if (rst) begin
            meta_ff    <= {NUM_ROS{1'b0}};
            sync_ff    <= {NUM_ROS{1'b0}};
            entropy_bit <= 1'b0;
        end
        else begin
            meta_ff     <= ro_bits_async;
            sync_ff     <= meta_ff;
            entropy_bit <= ^sync_ff;
        end
    end

endmodule
