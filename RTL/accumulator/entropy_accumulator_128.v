`timescale 1ns / 1ps

module entropy_accumulator_128 (
    input  wire         clk,
    input  wire         rst,

    // One valid entropy bit per sample
    input  wire         bit_valid,
    input  wire         entropy_bit,

    // 128-bit accumulated raw entropy
    output reg  [127:0] raw_entropy,

    // Goes HIGH for one clock when 128 bits are collected
    output reg          raw_valid
);

    reg [127:0] shift_reg;
    reg [7:0]   bit_count;

    always @(posedge clk) begin

        if (rst) begin
            shift_reg  <= 128'b0;
            bit_count  <= 8'd0;
            raw_entropy <= 128'b0;
            raw_valid   <= 1'b0;
        end

        else begin

            // Default: raw_valid is only a one-clock pulse
            raw_valid <= 1'b0;

            if (bit_valid) begin

                // Shift in the new entropy bit
                shift_reg <= {shift_reg[126:0], entropy_bit};

                if (bit_count == 8'd127) begin

                    // The 128th bit completes the block
                    raw_entropy <= {shift_reg[126:0], entropy_bit};

                    raw_valid <= 1'b1;

                    // Start collecting the next 128-bit block
                    bit_count <= 8'd0;
                end

                else begin
                    bit_count <= bit_count + 1'b1;
                end
            end
        end
    end

endmodule
