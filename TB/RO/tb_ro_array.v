`timescale 1ns / 1ps

module tb_ro_array;

    reg enable;
    wire [49:0] ro_bits;

    ro_array dut (
        .enable(enable),
        .ro_bits(ro_bits)
    );

    initial begin
        enable = 1'b0;
        #50;

        if (ro_bits !== 50'b0)
            $display("[FAIL] RO outputs are not disabled");

        enable = 1'b1;
        #100;

        $display("RO outputs = %b", ro_bits);

        $display("[PASS] 50-RO array instantiated");
        $finish;
    end

endmodule
