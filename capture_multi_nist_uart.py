import serial
import time
from pathlib import Path

# ============================================================
# FPGA UART TRNG MULTI-SEQUENCE NIST CAPTURE
# Captures multiple independent 1,048,576-bit streams.
# Creates:
#   1) Separate .bin and .txt files for each sequence
#   2) One combined ASCII .txt file for official NIST STS
# ============================================================

PORT = "COM7"
BAUD = 115200

NUM_STREAMS = 10
TARGET_BITS_PER_STREAM = 1_048_576
TARGET_BYTES_PER_STREAM = TARGET_BITS_PER_STREAM // 8

OUT_DIR = Path("C:/Users/gsaiv/RRAM/nist_multi_capture")
COMBINED_TXT = OUT_DIR / "trng_output_nist_10seq.txt"


def bytes_to_bit_string(data: bytes) -> str:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append(str((byte >> i) & 1))
    return "".join(bits)


def capture_exact_bytes(ser: serial.Serial, target_bytes: int, stream_index: int) -> bytes:
    data = bytearray()

    while len(data) < target_bytes:
        remaining = target_bytes - len(data)
        chunk = ser.read(min(4096, remaining))

        if chunk:
            data.extend(chunk)
            print(
                f"Stream {stream_index:02d}: "
                f"{len(data):,} / {target_bytes:,} bytes "
                f"({len(data) * 8:,} / {target_bytes * 8:,} bits)",
                end="\r",
            )

    print()
    return bytes(data)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("==============================================")
    print("      FPGA TRNG MULTI-SEQUENCE NIST CAPTURE")
    print("==============================================")
    print(f"Port                  : {PORT}")
    print(f"Baud rate             : {BAUD}")
    print(f"Streams               : {NUM_STREAMS}")
    print(f"Bits per stream       : {TARGET_BITS_PER_STREAM:,}")
    print(f"Bytes per stream      : {TARGET_BYTES_PER_STREAM:,}")
    print(f"Total bits            : {NUM_STREAMS * TARGET_BITS_PER_STREAM:,}")
    print(f"Output folder         : {OUT_DIR}")
    print()
    print("Before starting:")
    print("  1. Program the FPGA bitstream.")
    print("  2. Close PuTTY or any other serial monitor.")
    print("  3. Set SW0 ON to enable TRNG.")
    print("  4. Reset FPGA if needed.")
    print()

    with serial.Serial(PORT, BAUD, bytesize=8, parity="N", stopbits=1, timeout=2) as ser:
        print(f"Connected to {PORT} at {BAUD} baud")
        print("Starting capture in 3 seconds...")
        time.sleep(3)

        ser.reset_input_buffer()

        with open(COMBINED_TXT, "w", newline="") as combined:
            for stream_index in range(1, NUM_STREAMS + 1):
                print()
                print(f"--- Capturing stream {stream_index:02d}/{NUM_STREAMS:02d} ---")

                data = capture_exact_bytes(ser, TARGET_BYTES_PER_STREAM, stream_index)

                if len(data) != TARGET_BYTES_PER_STREAM:
                    raise RuntimeError(f"Stream {stream_index}: incorrect byte count {len(data)}")

                bit_string = bytes_to_bit_string(data)

                if len(bit_string) != TARGET_BITS_PER_STREAM:
                    raise RuntimeError(f"Stream {stream_index}: incorrect bit count {len(bit_string)}")

                bin_file = OUT_DIR / f"trng_seq{stream_index:02d}.bin"
                txt_file = OUT_DIR / f"trng_seq{stream_index:02d}.txt"

                with open(bin_file, "wb") as f:
                    f.write(data)

                with open(txt_file, "w", newline="") as f:
                    f.write(bit_string)

                # Official NIST STS expects the bitstreams concatenated with no separators.
                combined.write(bit_string)

                print(f"Saved binary : {bin_file}")
                print(f"Saved NIST txt: {txt_file}")

    print()
    print("==============================================")
    print("              CAPTURE COMPLETE")
    print("==============================================")
    print(f"Separate files : {OUT_DIR}")
    print(f"Combined file  : {COMBINED_TXT}")
    print(f"Streams        : {NUM_STREAMS}")
    print(f"Bits/stream    : {TARGET_BITS_PER_STREAM:,}")
    print(f"Total bits     : {NUM_STREAMS * TARGET_BITS_PER_STREAM:,}")
    print()
    print("Use this combined file in WSL NIST STS:")
    print("  /mnt/c/Users/gsaiv/RRAM/nist_multi_capture/trng_output_nist_10seq.txt")
    print("==============================================")


if __name__ == "__main__":
    main()
