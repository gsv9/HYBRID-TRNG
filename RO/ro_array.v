`timescale 1ns / 1ps

// 50-RO array:
//   17 x 3-stage
//   17 x 5-stage
//   16 x 7-stage
//
// For the low-power version, all oscillators share one enable.
// Power gating/banking should be added only after this baseline is
// characterized, because switching RO banks changes the entropy source.

module ro_array #(
    parameter integer NUM_3STAGE = 17,
    parameter integer NUM_5STAGE = 17,
    parameter integer NUM_7STAGE = 16
)(
    input  wire enable,
    output wire [49:0] ro_bits
);

    localparam integer TOTAL =
        NUM_3STAGE + NUM_5STAGE + NUM_7STAGE;

    initial begin
        if (TOTAL != 50)
            $error("RO array must contain exactly 50 oscillators");
    end

    genvar i;

    generate
        for (i = 0; i < NUM_3STAGE; i = i + 1) begin : gen_ro3
            ring_oscillator #(.STAGES(3)) u_ro (
                .enable(enable),
                .ro_out(ro_bits[i])
            );
        end

        for (i = 0; i < NUM_5STAGE; i = i + 1) begin : gen_ro5
            ring_oscillator #(.STAGES(5)) u_ro (
                .enable(enable),
                .ro_out(ro_bits[NUM_3STAGE+i])
            );
        end

        for (i = 0; i < NUM_7STAGE; i = i + 1) begin : gen_ro7
            ring_oscillator #(.STAGES(7)) u_ro (
                .enable(enable),
                .ro_out(ro_bits[NUM_3STAGE+NUM_5STAGE+i])
            );
        end
    endgenerate

endmodule
