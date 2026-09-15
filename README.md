# Compact Dual-Source TRNG Using Ring Oscillators and RRAM RTN for AES-Based Key Generation

This repository contains the RTL, testbenches, FPGA validation scripts, and reports for a compact FPGA TRNG prototype. The design combines ring-oscillator entropy with a behavioral RRAM random telegraph noise model, accumulates entropy into 128-bit blocks, conditions the data using AES-128 CBC-MAC style conditioning, and transmits the conditioned 128-bit output through UART.

## Architecture

```text
Ring Oscillator Entropy + Behavioral RRAM RTN
                 |
                 v
        Hybrid Entropy Source
                 |
                 v
        128-bit Accumulator
                 |
                 v
 AES-128 CBC-MAC Conditioner
                 |
                 v
          UART Output
```

## Target Platform

- Board: Digilent Arty A7-100T
- FPGA part: `xc7a100tcsg324-1`
- UART: 115200 baud, 8-N-1

## Main RTL Files

- `RTL/rram_ro_trng_aes_uart_top.v` - final FPGA top module with hybrid TRNG, AES conditioner, and UART output.
- `RTL/aes128_encrypt.v` - iterative AES-128 encryption core.
- `RTL/aes_cbc_mac_conditioner.v` - AES CBC-MAC style conditioning block.
- `RTL/entropy_accumulator_128.v` - collects entropy into 128-bit blocks.
- `RTL/rram_ro_hybrid.v` - combines RRAM and RO entropy sources.
- `RTL/RRAM/*.v` - behavioral RRAM/RTN model.
- `RTL/RO_TEST/*.v` - banked ring oscillator entropy source.
- `RTL/uart_tx.v` - UART transmitter.

## Testbenches

- `TB/tb_aes128_encrypt.v` - AES-128 known-answer verification.
- `TB/tb_entropy_accumulator_128.v` - accumulator verification.
- `TB/tb_rram_ro_hybrid_accumulator.v` - hybrid accumulator verification.
- `TB/RRAM/*.v` and `TB/RO/*.v` - source-level testbenches.

## FPGA Implementation Results

Final implemented design results on Arty A7-100T:

| Metric | Result |
| --- | ---: |
| Total on-chip power | 0.118 W |
| Dynamic power | 0.027 W |
| Static power | 0.092 W |
| LUT utilization | 909 / 63400 = 1.43% |
| FF utilization | 988 / 126800 = 0.78% |
| BRAM utilization | 5.5 / 135 = 4.07% |
| IO utilization | 5 / 210 = 2.38% |
| Implemented timing WNS | +2.245 ns |

Reports are stored in:

- `final_reports/synthesis_reports/`
- `final_reports/implementation_reports/`

## Randomness Validation

Hardware UART output was captured from the FPGA and tested using both preliminary Python analysis and the official NIST SP 800-22 Statistical Test Suite.

Final official NIST STS run:

- 10 independent bitstreams
- 1,048,576 bits per bitstream
- Total tested bits: 10,485,760
- Result: PASS based on NIST proportion and p-value uniformity criteria.

Useful scripts:

- `capture_trng_uart.py` - capture UART output.
- `capture_trng_for_nist.py` - capture one NIST-sized stream.
- `capture_multi_nist_uart.py` - capture 10 NIST-sized streams and create a combined NIST input file.
- `analyze_trng.py` - preliminary randomness analysis.
- `compare_runs.py` - compare two independent hardware captures.
- `nist_style_tests.py` - Python-based NIST-style preliminary tests.

## Notes

- The Arty A7 does not contain physical RRAM. The RRAM block in this project is a behavioral RTN model.
- The ring oscillator source is implemented in FPGA fabric and requires Vivado combinational-loop constraints.
- Captured random streams and generated Vivado build folders are intentionally excluded from Git by `.gitignore`.
