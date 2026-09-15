import math
from collections import Counter

INPUT_FILE = "C:/Users/gsaiv/RRAM/trng_output.bin"

with open(INPUT_FILE, "rb") as f:
    data = f.read()

bits = []
for byte in data:
    for i in range(7, -1, -1):
        bits.append((byte >> i) & 1)

n = len(bits)
ones = sum(bits)
zeros = n - ones

print("====================================")
print("TRNG BASIC RANDOMNESS ANALYSIS")
print("====================================")
print(f"Input file      : {INPUT_FILE}")
print(f"Bytes           : {len(data)}")
print(f"Bits            : {n}")
print(f"Zeros           : {zeros}")
print(f"Ones            : {ones}")
print(f"One ratio       : {ones / n:.6f}")
print(f"Zero ratio      : {zeros / n:.6f}")
print(f"Bias from 0.5   : {abs((ones / n) - 0.5):.6f}")
print()

# Frequency / monobit test approximation
s_obs = abs(ones - zeros) / math.sqrt(n)
p_monobit = math.erfc(s_obs / math.sqrt(2))

print("Frequency / Monobit Test")
print(f"S_obs           : {s_obs:.6f}")
print(f"p-value         : {p_monobit:.6f}")
print("Result          :", "PASS" if p_monobit >= 0.01 else "FAIL")
print()

# Runs test
pi = ones / n
tau = 2 / math.sqrt(n)

print("Runs Test")
if abs(pi - 0.5) >= tau:
    print("Result          : FAIL")
    print("Reason          : Pi too far from 0.5 for runs test")
else:
    runs = 1
    for i in range(1, n):
        if bits[i] != bits[i - 1]:
            runs += 1

    numerator = abs(runs - (2 * n * pi * (1 - pi)))
    denominator = 2 * math.sqrt(2 * n) * pi * (1 - pi)
    p_runs = math.erfc(numerator / denominator)

    print(f"Runs            : {runs}")
    print(f"p-value         : {p_runs:.6f}")
    print("Result          :", "PASS" if p_runs >= 0.01 else "FAIL")
print()

# Byte distribution
counts = Counter(data)
expected = len(data) / 256
chi2 = sum(((counts.get(i, 0) - expected) ** 2) / expected for i in range(256))

print("Byte Distribution")
print(f"Unique bytes    : {len(counts)} / 256")
print(f"Chi-square      : {chi2:.3f}")
print("Note            : For 255 dof, expected chi-square is around 255")
print()

# Shannon entropy per byte
entropy = 0.0
for count in counts.values():
    p = count / len(data)
    entropy -= p * math.log2(p)

print("Shannon Entropy")
print(f"Entropy/byte    : {entropy:.6f} bits")
print("Ideal           : 8.000000 bits")
print()

# Serial 2-bit pattern counts
pairs = Counter()
for i in range(0, n - 1, 2):
    value = (bits[i] << 1) | bits[i + 1]
    pairs[value] += 1

print("2-bit Serial Pattern Counts")
for value in range(4):
    print(f"{value:02b}              : {pairs[value]}")
print()

print("====================================")