FILE1 = "C:/Users/gsaiv/RRAM/trng_run1.bin"
FILE2 = "C:/Users/gsaiv/RRAM/trng_run2.bin"

with open(FILE1, "rb") as f:
    a = f.read()

with open(FILE2, "rb") as f:
    b = f.read()

n = min(len(a), len(b))

same_bytes = sum(1 for i in range(n) if a[i] == b[i])
diff_bytes = n - same_bytes

bit_diff = 0
total_bits = n * 8

for x, y in zip(a[:n], b[:n]):
    bit_diff += (x ^ y).bit_count()

print("====================================")
print("TRNG RUN-TO-RUN COMPARISON")
print("====================================")
print(f"File 1 bytes       : {len(a)}")
print(f"File 2 bytes       : {len(b)}")
print(f"Compared bytes     : {n}")
print(f"Identical files    : {a == b}")
print()
print(f"Same byte positions: {same_bytes}")
print(f"Diff byte positions: {diff_bytes}")
print(f"Same byte ratio    : {same_bytes / n:.6f}")
print(f"Diff byte ratio    : {diff_bytes / n:.6f}")
print()
print(f"Bit differences    : {bit_diff}")
print(f"Total bits compared: {total_bits}")
print(f"Bit difference rate: {bit_diff / total_bits:.6f}")
print("Ideal bit diff rate: about 0.500000")
print("====================================")