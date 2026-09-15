import serial
import time

PORT = "COM7"
BAUD = 115200
OUTPUT_FILE = "C:/Users/gsaiv/RRAM/trng_output.bin"

TARGET_BYTES = 125000
# 125000 bytes = 1,000,000 bits

with serial.Serial(PORT, BAUD, bytesize=8, parity="N", stopbits=1, timeout=2) as ser:
    print(f"Connected to {PORT} at {BAUD} baud")
    print("Reset FPGA if needed, set SW0 ON.")
    time.sleep(2)

    data = bytearray()

    while len(data) < TARGET_BYTES:
        chunk = ser.read(min(4096, TARGET_BYTES - len(data)))
        if chunk:
            data.extend(chunk)
            print(f"Captured {len(data)} / {TARGET_BYTES} bytes", end="\r")

    with open(OUTPUT_FILE, "wb") as f:
        f.write(data)

print()
print(f"Saved {len(data)} bytes to {OUTPUT_FILE}")