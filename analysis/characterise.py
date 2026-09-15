"""
Entropy characterisation of the RRAM raw bit stream.

Runs both suites over one stream and prints a report whose claims are bounded by
what the data can actually support. Read the CLAIM BOUNDARY section of the output
before quoting any number from it.

Bit sources
-----------
  --model            the bit-exact golden model of rram_cell + the stochastic
                     testbench stimulus (default). This is the CURRENT design,
                     LFSR-driven, and is expected to look terrible.
  --file PATH        a captured stream: '0'/'1' text, or raw bytes with --bytes.
  --control NAME     urandom | lfsr8 | alternating, for comparison.

Usage:
    python3 characterise.py --model --n 100000
    python3 characterise.py --file capture.bin --bytes --n 1000000
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nist_sp800_22 as s22
import sp800_90b as s90


# ----------------------------------------------------------------------------
# structural diagnostics
#
# These come first because they are DECISIVE in a way the statistical suites are
# not. If a stream is exactly periodic then its entropy is bounded by the period
# regardless of what any estimator reports, and no amount of downstream
# conditioning creates entropy that the source never had. A period found here
# ends the analysis; the suites below are then only of diagnostic interest.
# ----------------------------------------------------------------------------

def exact_period(bits, min_repeats=3):
    """Find EVENTUAL periodicity: a transient prefix followed by exact repetition.

    Returns (transient, period) or (None, None).

    Requiring the whole stream to be periodic is the wrong test and it gave the
    wrong answer here. A finite state machine driven by a periodic stimulus is
    eventually periodic, but it first has to walk from its reset state into the
    limit cycle, and anything that ratchets - a threshold drifting toward a
    clamp, a counter saturating - makes that walk long. The RRAM stream is exactly
    periodic with period 170 from sample ~1911 onward, yet a whole-stream scan
    reports no period at all and would have been quietly reassuring.

    So: locate the limit cycle in the tail first, then walk the start backwards to
    find where it began. min_repeats guards against calling a short coincidence a
    period.
    """
    n = len(bits)
    tail_start = n // 2
    tail = bits[tail_start:]
    m = len(tail)
    period = None
    for p in range(1, m // min_repeats + 1):
        if all(tail[i] == tail[i + p] for i in range(m - p)):
            period = p
            break
    if period is None:
        return None, None
    # earliest index from which the period holds all the way to the end
    lo, hi = 0, tail_start
    while lo < hi:
        mid = (lo + hi) // 2
        if all(bits[i] == bits[i + period] for i in range(mid, n - period)):
            hi = mid
        else:
            lo = mid + 1
    return lo, period


def autocorrelation(bits, max_lag=64):
    """Pearson correlation of the stream with itself at lags 1..max_lag.

    Reported as a z-score: for an IID stream each correlation is approximately
    N(0, 1/sqrt(n)), so |z| > 4 at any single lag is strong evidence of
    structure. Bonferroni over max_lag lags puts the 1% threshold near 3.6.
    """
    n = len(bits)
    x = [2 * b - 1 for b in bits]          # +-1 removes the mean if balanced
    mean = sum(x) / n
    var = sum((v - mean) ** 2 for v in x) / n
    out = []
    if var <= 0:
        return out
    for lag in range(1, min(max_lag, n // 4) + 1):
        m = n - lag
        cov = sum((x[i] - mean) * (x[i + lag] - mean) for i in range(m)) / m
        r = cov / var
        out.append((lag, r, r * math.sqrt(m)))
    return out


def bit_summary(bits):
    n = len(bits)
    ones = sum(bits)
    runs = 1 + sum(1 for i in range(1, n) if bits[i] != bits[i - 1])
    return n, ones, ones / n, runs


# ----------------------------------------------------------------------------
# bit sources
# ----------------------------------------------------------------------------

def from_model(n, pre_advance=1):
    """Golden model of the CURRENT design.

    pre_advance=1 is the silicon-of-record and must stay the default. rst deasserts
    at t=20, which races the t=20 negedge, so the LFSRs advance exactly once before
    the first active posedge; pre_advance=1 reproduces the XSim stream bit-for-bit
    while other values agree only 52-56% of the time.

    This is not a detail that can be left to a default argument elsewhere. The
    model's own default is 0, and characterising with it describes a design that
    does not exist: because gcd(6, 255) = 3 the threshold-update instants only ever
    visit a fixed sub-orbit of the LFSR, and which sub-orbit depends on this phase.
    Measured over 20,000 samples:

        pre_advance   set_thr      reset_thr    thresholds equal from
             0        145 -> 180   110 -> 180   sample 1911   (drifts UP, clamps at hi)
             1        145 ->  82   110 ->  82   sample 1055   (drifts DOWN, clamps at lo)
             2        145 -> 180   110 -> 180   sample 1903
             3        145 -> 180   110 -> 180   sample 1829

    So the drift DIRECTION is an accident of reset phase - three of four phases run
    to the ceiling and only the real one runs to the floor. The direction is
    therefore not the bug and flipping a sign would not fix anything. What is
    phase-independent, and is the actual defect, is the two facts that hold in every
    row: a net drift exists at all, and the two thresholds become equal early and
    stay equal forever after.
    """
    import rram_model
    bits, cycles = rram_model.run(n_samples=n, pre_advance=pre_advance)
    return bits, (f"golden model of rram_cell, LFSR stimulus, pre_advance="
                  f"{pre_advance} (silicon-of-record), {cycles} clock cycles")


def from_file(path, as_bytes, n):
    raw = open(path, "rb").read()
    if as_bytes:
        bits = []
        for byte in raw:
            for k in range(7, -1, -1):
                bits.append((byte >> k) & 1)
                if len(bits) == n:
                    return bits, f"{path} ({len(raw)} bytes, MSB first)"
        return bits, f"{path} ({len(raw)} bytes, MSB first)"
    bits = [1 if c in b"1" else 0 for c in raw if c in b"01"][:n]
    return bits, f"{path} ({len(bits)} bits of text)"


def from_control(name, n):
    if name == "urandom":
        bits = []
        for byte in os.urandom(n // 8 + 1):
            for k in range(7, -1, -1):
                bits.append((byte >> k) & 1)
                if len(bits) == n:
                    break
        return bits[:n], "os.urandom reference"
    if name == "alternating":
        return [i & 1 for i in range(n)], "alternating 0101 reference"
    if name == "lfsr8":
        st = 0b10110101
        out = []
        for _ in range(n):
            out.append(st & 1)
            fb = ((st >> 7) ^ (st >> 5) ^ (st >> 4) ^ (st >> 3)) & 1
            st = ((st << 1) | fb) & 0xFF
        return out, "8-bit LFSR, period 255 reference"
    raise SystemExit(f"unknown control {name}")


# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--bytes", action="store_true")
    ap.add_argument("--control")
    ap.add_argument("--n", type=int, default=100000)
    ap.add_argument("--fast", action="store_true",
                    help="omit the slowest tests/estimators")
    ap.add_argument("--no-period", action="store_true",
                    help="skip the O(n^2) exact-period scan")
    a = ap.parse_args()

    if a.file:
        bits, origin = from_file(a.file, a.bytes, a.n)
    elif a.control:
        bits, origin = from_control(a.control, a.n)
    else:
        bits, origin = from_model(a.n)

    n, ones, p1, nruns = bit_summary(bits)
    print("=" * 78)
    print("RRAM RAW STREAM CHARACTERISATION")
    print("=" * 78)
    print(f"  source : {origin}")
    print(f"  length : {n} bits")
    print(f"  ones   : {ones}  P(1) = {p1:.6f}")
    print(f"  runs   : {nruns}  (an IID balanced stream expects ~{n/2:.0f})")

    print()
    print("-" * 78)
    print("1. STRUCTURAL DIAGNOSTICS  (decisive - read these first)")
    print("-" * 78)
    period = None
    transient = None
    if not a.no_period:
        transient, period = exact_period(bits)
    if period:
        reps = (n - transient) // period
        print(f"  EVENTUALLY PERIODIC: period {period} bits, "
              f"transient {transient} bits.")
        print(f"  From sample {transient} onward the stream repeats exactly, "
              f"confirmed over {reps} repeats.")
        print(f"  Entropy rate is therefore ZERO. The stream carries at most the")
        print(f"  information in one period plus the transient, which does not grow")
        print(f"  with run length - collecting 10x more bits adds nothing. No")
        print(f"  conditioning stage can repair this: hashing a periodic input")
        print(f"  yields a periodic output. Everything below is diagnostic only.")
    elif not a.no_period:
        print(f"  No eventual periodicity found (searched periods up to "
              f"{n // 2 // 3} bits in the second half of the stream).")
    else:
        print("  (period scan skipped)")
    ac = autocorrelation(bits)
    if ac:
        worst = max(ac, key=lambda t: abs(t[2]))
        big = [t for t in ac if abs(t[2]) > 3.6]
        print(f"  Autocorrelation over lags 1..{len(ac)}: largest |z| = {abs(worst[2]):.1f}"
              f" at lag {worst[0]} (r = {worst[1]:+.4f})")
        print(f"  {len(big)} of {len(ac)} lags exceed |z| = 3.6 "
              f"(Bonferroni 1% threshold; an IID stream expects ~0)")
        if big:
            shown = ", ".join(f"lag {l}: z={z:+.1f}" for l, _, z in big[:8])
            print(f"    {shown}{' ...' if len(big) > 8 else ''}")

    print()
    print("-" * 78)
    print("2. SP 800-90B MIN-ENTROPY ESTIMATION  (how much entropy is there?)")
    print("-" * 78)
    r90 = s90.run_all(bits, fast=a.fast)
    print(s90.format_report(r90))

    # Supplementary, deliberately outside the assessed figure above.
    #
    # The compliant lag estimator uses the D=128 that SP 800-90B mandates, and
    # that D cannot express a period longer than 128 - on this very stream, whose
    # period is 170 and whose entropy rate is zero, it reports 0.47 bits/bit. The
    # standard's assessed number is therefore printed unmodified (it has to be, to
    # remain comparable) and the tighter bound is printed here, labelled, so that
    # neither figure can be mistaken for the other.
    lx = s90.lag_extended(bits, hint=period)
    lc = s90.get(r90, "Lag predictor")
    print()
    print(f"  supplementary (NOT part of the assessed figure, non-standard D):")
    print(f"    {lx.name:<30} {lx.min_entropy:8.6f}   {lx.detail}")
    if (lc is not None and lc.min_entropy == lc.min_entropy
            and lx.min_entropy == lx.min_entropy
            and lc.min_entropy > lx.min_entropy + 1e-6):
        print(f"    The compliant D=128 figure ({lc.min_entropy:.6f}) is looser than this")
        print(f"    by {lc.min_entropy / max(lx.min_entropy, 1e-12):.0f}x. Quote the compliant one, but do not")
        print(f"    rely on it to detect periodicity - it structurally cannot see")
        print(f"    a period above 128.")

    print()
    print("-" * 78)
    print("3. SP 800-22 STATISTICAL TESTS  (is it distinguishable from random?)")
    print("-" * 78)
    r22 = s22.run_all(bits, fast=a.fast)
    print(s22.format_report(r22))

    npass, nfail, nadv, nskip = s22.tally(r22)
    h = s90.min_entropy(r90)

    print()
    print("=" * 78)
    print("CLAIM BOUNDARY  -  what this output does and does not support")
    print("=" * 78)
    print(f"  Measured H_min = {h:.6f} bits/bit at n = {n}.")
    print(f"  Ideal-source ceiling at this n = {s90.ideal_collision_hmin(n):.4f}"
          f" (the collision estimator cannot score 1.0 on a finite sample), so")
    print(f"  H_min must always be quoted WITH its sample size.")
    print()
    if nadv or nskip:
        print(f"  {nadv} test(s) advisory and {nskip} skipped because n = {n} is below")
        print(f"  the length their reference distributions require. SP 800-22 is")
        print(f"  specified for n >= 1e6; below that, several tests reject good data")
        print(f"  measurably too often, so their verdicts are withheld rather than")
        print(f"  reported. A complete suite result REQUIRES a stream of >= 1e6 bits.")
        print()
    print("  Passing SP 800-22 is not an entropy claim. A counter through SHA-256")
    print("  and a 32-bit LFSR both pass every test in it with H_min near 1.0 while")
    print("  having exactly zero entropy. These suites can refute randomness; they")
    print("  cannot establish it. An entropy claim rests on a physical argument")
    print("  about the source, supported by tests that fail to refute it.")
    if period:
        print()
        print(f"  For THIS stream the question does not arise: it is eventually")
        print(f"  periodic with period {period} from sample {transient}, so its entropy")
        print(f"  rate is zero and the only defensible claim is that the datapath")
        print(f"  works, not that it produces entropy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
