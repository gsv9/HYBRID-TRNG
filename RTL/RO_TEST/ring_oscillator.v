`timescale 1ns / 1ps

module ring_oscillator #(
    parameter integer STAGES    = 3,
    parameter integer SIM_DELAY = 1
)(
    input  wire enable,
    output wire ro_out
);

    initial begin
        if ((STAGES != 3) && (STAGES != 5) && (STAGES != 7))
            $error("STAGES must be 3, 5, or 7");
    end

`ifndef SYNTHESIS
    reg ro_reg;
    integer delay_ns;
    integer jitter;
    initial ro_reg = 1'b0;

    always begin
        if (!enable) begin
            ro_reg = 1'b0;
            @(posedge enable);
        end
        else begin
            jitter = $urandom_range(0, 1);
            delay_ns = (SIM_DELAY * STAGES) + jitter;
            if (delay_ns < 1)
                delay_ns = 1;
            #(delay_ns);
            if (enable)
                ro_reg = ~ro_reg;
            else
                ro_reg = 1'b0;
        end
    end

    assign ro_out = ro_reg;

`else
    (* KEEP = "TRUE", DONT_TOUCH = "TRUE" *)
    wire [STAGES-1:0] ro;
    genvar i;

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

    assign ro_out = enable ? ro[STAGES-1] : 1'b0;
`endif
endmodule
