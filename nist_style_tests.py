import math
from collections import Counter

import numpy as np
from scipy.special import gammaincc

import sys
INPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "C:/Users/gsaiv/RRAM/trng_run1.bin"
ALPHA = 0.01


def load_bits(path):
    with open(path, "rb") as f:
        data = f.read()
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    return data, bits.astype(np.uint8)


def result_line(name, p_value, extra=""):
    status = "PASS" if p_value >= ALPHA else "FAIL"
    suffix = f" | {extra}" if extra else ""
    return f"{name:<28} p-value = {p_value:.6f} | {status}{suffix}"


def frequency_monobit(bits):
    n = len(bits)
    signed = 2 * bits.astype(np.int16) - 1
    s_obs = abs(int(np.sum(signed))) / math.sqrt(n)
    p_value = math.erfc(s_obs / math.sqrt(2))
    return p_value, f"S_obs={s_obs:.6f}"


def runs_test(bits):
    n = len(bits)
    pi = float(np.mean(bits))
    tau = 2 / math.sqrt(n)
    if abs(pi - 0.5) >= tau:
        return 0.0, f"pi={pi:.6f}, pi too far from 0.5"
    runs = 1 + int(np.sum(bits[1:] != bits[:-1]))
    numerator = abs(runs - (2 * n * pi * (1 - pi)))
    denominator = 2 * math.sqrt(2 * n) * pi * (1 - pi)
    p_value = math.erfc(numerator / denominator)
    return p_value, f"runs={runs}, pi={pi:.6f}"


def fft_spectral_test(bits):
    n = len(bits)
    x = 2 * bits.astype(np.int16) - 1
    spectrum = np.fft.fft(x)
    magnitudes = np.abs(spectrum[: n // 2])
    threshold = math.sqrt(math.log(1 / 0.05) * n)
    n0 = 0.95 * n / 2
    n1 = int(np.sum(magnitudes < threshold))
    d = (n1 - n0) / math.sqrt(n * 0.95 * 0.05 / 4)
    p_value = math.erfc(abs(d) / math.sqrt(2))
    return p_value, f"N1={n1}, N0={n0:.2f}, d={d:.6f}"


def pattern_counts(bits, m):
    n = len(bits)
    extended = np.concatenate([bits, bits[: m - 1]])
    counts = np.zeros(1 << m, dtype=np.int64)
    value = 0
    for i in range(m):
        value = (value << 1) | int(extended[i])
    counts[value] += 1
    mask = (1 << m) - 1
    for i in range(1, n):
        value = ((value << 1) & mask) | int(extended[i + m - 1])
        counts[value] += 1
    return counts


def psi2(bits, m):
    if m <= 0:
        return 0.0
    n = len(bits)
    counts = pattern_counts(bits, m)
    return (np.sum(counts * counts) * (2**m) / n) - n


def serial_test(bits, m=2):
    psim = psi2(bits, m)
    psim1 = psi2(bits, m - 1)
    psim2 = psi2(bits, m - 2)
    delta1 = psim - psim1
    delta2 = psim - (2 * psim1) + psim2
    p1 = gammaincc(2 ** (m - 2), delta1 / 2)
    p2 = gammaincc(0.5, delta2 / 2)
    return p1, p2, f"m={m}, delta1={delta1:.6f}, delta2={delta2:.6f}"


def approximate_entropy_test(bits, m=10):
    n = len(bits)
    c_m = pattern_counts(bits, m)
    c_m1 = pattern_counts(bits, m + 1)
    p_m = c_m / n
    p_m1 = c_m1 / n
    phi_m = float(np.sum(p_m[p_m > 0] * np.log(p_m[p_m > 0])))
    phi_m1 = float(np.sum(p_m1[p_m1 > 0] * np.log(p_m1[p_m1 > 0])))
    ap_en = phi_m - phi_m1
    chi_sq = 2 * n * (math.log(2) - ap_en)
    p_value = gammaincc(2 ** (m - 1), chi_sq / 2)
    return p_value, f"m={m}, ApEn={ap_en:.6f}, chi_sq={chi_sq:.6f}"


def byte_entropy(data):
    counts = Counter(data)
    entropy = 0.0
    for count in counts.values():
        p = count / len(data)
        entropy -= p * math.log2(p)
    expected = len(data) / 256
    chi2 = sum(((counts.get(i, 0) - expected) ** 2) / expected for i in range(256))
    return entropy, chi2, len(counts)


def main():
    data, bits = load_bits(INPUT_FILE)
    n = len(bits)
    ones = int(np.sum(bits))
    zeros = n - ones

    print("============================================================")
    print("NIST-STYLE RANDOMNESS TEST SUMMARY")
    print("============================================================")
    print(f"Input file      : {INPUT_FILE}")
    print(f"Bytes           : {len(data)}")
    print(f"Bits            : {n}")
    print(f"Zeros           : {zeros}")
    print(f"Ones            : {ones}")
    print(f"One ratio       : {ones / n:.6f}")
    print(f"Bias from 0.5   : {abs((ones / n) - 0.5):.6f}")
    print(f"Alpha           : {ALPHA}")
    print()

    p, extra = frequency_monobit(bits)
    print(result_line("Frequency Monobit", p, extra))
    p, extra = runs_test(bits)
    print(result_line("Runs", p, extra))
    p, extra = fft_spectral_test(bits)
    print(result_line("FFT Spectral", p, extra))
    p1, p2, extra = serial_test(bits, m=2)
    print(result_line("Serial p1", p1, extra))
    print(result_line("Serial p2", p2, extra))
    p, extra = approximate_entropy_test(bits, m=10)
    print(result_line("Approximate Entropy", p, extra))
    print()

    entropy, chi2, unique = byte_entropy(data)
    print("Supporting Byte-Level Statistics")
    print(f"Unique bytes    : {unique} / 256")
    print(f"Byte chi-square : {chi2:.3f}")
    print(f"Entropy/byte    : {entropy:.6f} bits")
    print("Ideal entropy   : 8.000000 bits")
    print("============================================================")


if __name__ == "__main__":
    main()
