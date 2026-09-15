import serial
import time

# ============================================================
# FPGA UART TRNG CAPTURE FOR NIST STS
# Captures exactly 1,048,576 bits = 131,072 bytes
# ============================================================

PORT = "COM7"
BAUD = 115200

BINARY_FILE = "C:/Users/gsaiv/RRAM/trng_output_run2.bin"
NIST_FILE = "C:/Users/gsaiv/RRAM/trng_output_run2.txt"

TARGET_BITS = 1_048_576
TARGET_BYTES = TARGET_BITS // 8

print("==============================================")
print("       FPGA TRNG NIST CAPTURE")
print("==============================================")
print(f"Port             : {PORT}")
print(f"Baud rate        : {BAUD}")
print(f"Target bits      : {TARGET_BITS:,}")
print(f"Target bytes     : {TARGET_BYTES:,}")
print()

with serial.Serial(
    PORT,
    BAUD,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=2
) as ser:

    print(f"Connected to {PORT} at {BAUD} baud")
    print()
    print("Reset FPGA if needed.")
    print("Set SW0 ON to enable TRNG.")
    print("Starting capture in 3 seconds...")
    time.sleep(3)

    ser.reset_input_buffer()

    data = bytearray()

    while len(data) < TARGET_BYTES:
        remaining = TARGET_BYTES - len(data)
        chunk = ser.read(min(4096, remaining))

        if chunk:
            data.extend(chunk)
            print(
                f"Captured {len(data):,} / "
                f"{TARGET_BYTES:,} bytes "
                f"({len(data) * 8:,} / {TARGET_BITS:,} bits)",
                end="\r"
            )

print()
print()

if len(data) != TARGET_BYTES:
    raise RuntimeError(f"Incorrect capture size: {len(data)} bytes")

with open(BINARY_FILE, "wb") as f:
    f.write(data)

print("Binary file saved:")
print(f"  {BINARY_FILE}")

with open(NIST_FILE, "w") as f:
    for byte in data:
        for i in range(7, -1, -1):
            f.write(str((byte >> i) & 1))

print()
print("NIST ASCII bit file saved:")
print(f"  {NIST_FILE}")

print()
print("==============================================")
print("             CAPTURE COMPLETE")
print("==============================================")
print(f"Bytes captured : {len(data):,}")
print(f"Bits captured  : {TARGET_BITS:,}")
print()
print("[PASS] Exactly 1,048,576 bits captured.")
print("[PASS] Binary file created.")
print("[PASS] NIST ASCII bit file created.")
print("==============================================")