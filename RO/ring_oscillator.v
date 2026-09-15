`timescale 1ns / 1ps

// FPGA ring oscillator primitive.
// The enabled loop contains an ODD number of inverter LUTs.
// This module is intended for synthesis/implementation on Xilinx FPGA.
// SIM_DELAY is only a simulation aid; simulation jitter is NOT physical entropy.

module ring_oscillator #(
    parameter integer STAGES   = 3,
    parameter integer SIM_DELAY = 1
)(
    input  wire enable,
    output wire ro_out
);

    // 3, 5, and 7 are the supported configurations for this project.
    initial begin
        if ((STAGES != 3) && (STAGES != 5) && (STAGES != 7))
            $error("STAGES must be 3, 5, or 7");
    end

    (* KEEP = "TRUE", DONT_TOUCH = "TRUE" *)
    wire [STAGES-1:0] ro;

    genvar i;

    // First LUT is the feedback inverter and also gates the oscillator.
    // When enable=1: ro[0] = ~ro[STAGES-1].
    // The loop therefore has STAGES inversions.
    (* KEEP = "TRUE", DONT_TOUCH = "TRUE" *)
    LUT1 #(.INIT(2'b01)) feedback_lut (
        .I0(enable ? ro[STAGES-1] : 1'b0),
        .O(ro[0])
    );

    generate
        for (i = 0; i < STAGES-1; i = i + 1) begin : gen_inv
            (* KEEP = "TRUE", DONT_TOUCH = "TRUE" *)
            LUT1 #(.INIT(2'b01)) inv_lut (
                .I0(ro[i]),
                .O(ro[i+1])
            );
        end
    endgenerate

    assign ro_out = ro[STAGES-1];

endmodule
