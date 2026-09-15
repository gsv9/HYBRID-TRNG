`timescale 1ns / 1ps

module ro_array_banked #(
    parameter integer NUM_3STAGE = 17,
    parameter integer NUM_5STAGE = 17,
    parameter integer NUM_7STAGE = 16,
    parameter integer NUM_BANKS  = 5
)(
    input  wire       enable,
    input  wire [2:0] bank_sel,
    output wire [49:0] ro_bits
);

    // Exactly 50 ROs:
    //   17 x 3-stage
    //   17 x 5-stage
    //   16 x 7-stage
    //
    // Five banks of 10 ROs are used.
    // Each bank contains approximately the same mixture of RO lengths:
    //
    // Bank 0: 3-stage[0:3], 5-stage[0:2], 7-stage[0:2]   = 10
    // Bank 1: 3-stage[4:6], 5-stage[3:6], 7-stage[3:5]   = 10
    // Bank 2: 3-stage[7:9], 5-stage[7:9], 7-stage[6:8]   = 9
    // Bank 3: 3-stage[10:13], 5-stage[10:12], 7-stage[9:12] = 11
    // Bank 4: remaining ROs                                   = 10
    //
    // The simple implementation below instead assigns consecutive
    // physical indices to banks. The exact per-bank stage mix must be
    // checked statistically before making claims about equal entropy.

    wire bank0_en = enable && (bank_sel == 3'd0);
    wire bank1_en = enable && (bank_sel == 3'd1);
    wire bank2_en = enable && (bank_sel == 3'd2);
    wire bank3_en = enable && (bank_sel == 3'd3);
    wire bank4_en = enable && (bank_sel == 3'd4);

    genvar i;

    generate
        for (i = 0; i < 17; i = i + 1) begin : gen_ro3
            wire en_i;
            assign en_i = (i < 4)  ? bank0_en :
                          (i < 7)  ? bank1_en :
                          (i < 10) ? bank2_en :
                          (i < 14) ? bank3_en :
                                     bank4_en;
            ring_oscillator #(.STAGES(3)) ro3 (
                .enable(en_i),
                .ro_out(ro_bits[i])
            );
        end
    endgenerate

    generate
        for (i = 0; i < 17; i = i + 1) begin : gen_ro5
            wire en_i;
            assign en_i = (i < 3)  ? bank0_en :
                          (i < 7)  ? bank1_en :
                          (i < 10) ? bank2_en :
                          (i < 13) ? bank3_en :
                                     bank4_en;
            ring_oscillator #(.STAGES(5)) ro5 (
                .enable(en_i),
                .ro_out(ro_bits[17+i])
            );
        end
    endgenerate

    generate
        for (i = 0; i < 16; i = i + 1) begin : gen_ro7
            wire en_i;
            assign en_i = (i < 3)  ? bank0_en :
                          (i < 6)  ? bank1_en :
                          (i < 9)  ? bank2_en :
                          (i < 13) ? bank3_en :
                                     bank4_en;
            ring_oscillator #(.STAGES(7)) ro7 (
                .enable(en_i),
                .ro_out(ro_bits[34+i])
            );
        end
    endgenerate

endmodule
