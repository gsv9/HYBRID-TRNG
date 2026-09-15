"""
Toolchain validation against control streams with KNOWN answers.

This must be run and must pass before any number from these estimators is
quoted about a real source. The reasoning is simple: if the tooling cannot
detect a source that is definitely bad, it cannot vindicate a source that
might be good.

Controls and their expected verdicts:

  urandom       cryptographic quality   -> passes SP 800-22, H_min ~ 1.0
  biased p=0.70 known analytic answer   -> H_min ~ -log2(0.70) = 0.5146
  biased p=0.90 known analytic answer   -> H_min ~ -log2(0.90) = 0.1520
  alternating   period 2                -> fails almost everything, H_min ~ 0
  lfsr8         period 255              -> MUST be caught: near-perfect bias but
                                          zero entropy. This is the control that
                                          mirrors the RRAM testbench problem.
  lfsr32        period 2^32-1           -> passes everything, H_min ~ 1.0
  aes_ctr_like  counter through SHA-256 -> passes everything, H_min ~ 1.0

The last two controls are the most important ones in this file, and they are
expected to PASS. Both are fully deterministic with zero entropy, and no test
here can tell. That is not a defect in the tooling; it is a theorem. Statistical
testing can refute randomness, never establish it. Entropy claims rest on a
physical argument about the source, and the tests only catch sources whose
structure is short enough to be seen in the sample. Quote them accordingly.
"""

import hashlib
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nist_sp800_22 as s22
import sp800_90b as s90
import specfun


def bits_from_bytes(bs, n):
    out = []
    for byte in bs:
        for k in range(7, -1, -1):
            out.append((byte >> k) & 1)
            if len(out) == n:
                return out
    return out


def ctl_urandom(n):
    return bits_from_bytes(os.urandom(n // 8 + 1), n)


def ctl_biased(n, p):
    import random
    rng = random.Random(12345)
    return [1 if rng.random() < p else 0 for _ in range(n)]


def ctl_alternating(n):
    return [i & 1 for i in range(n)]


def ctl_lfsr(n, width, taps, seed=None):
    """Galois-style LFSR over `width` bits, emitting the LSB each step."""
    state = seed if seed is not None else (1 << (width - 1)) | 1
    out = []
    mask = (1 << width) - 1
    for _ in range(n):
        out.append(state & 1)
        fb = 0
        for t in taps:
            fb ^= (state >> t) & 1
        state = ((state << 1) | fb) & mask
    return out


def ctl_hash_counter(n):
    """A pure counter pushed through SHA-256 - the 'conditioning hides
    everything' control."""
    out = []
    i = 0
    while len(out) < n:
        blk = hashlib.sha256(i.to_bytes(8, "big")).digest()
        out.extend(bits_from_bytes(blk, min(256, n - len(out))))
        i += 1
    return out[:n]


CONTROLS = [
    ("urandom",        lambda n: ctl_urandom(n),                     "PASS all, H~1.0"),
    ("biased p=0.70",  lambda n: ctl_biased(n, 0.70),                "H~0.5146"),
    ("biased p=0.90",  lambda n: ctl_biased(n, 0.90),                "H~0.1520"),
    ("alternating",    lambda n: ctl_alternating(n),                 "FAIL, H~0"),
    ("lfsr8 (p=255)",  lambda n: ctl_lfsr(n, 8, (7, 5, 4, 3)),       "MUST be caught, H~0"),
    ("lfsr32",         lambda n: ctl_lfsr(n, 32, (31, 21, 1, 0)),    "PASS all, H~1.0"),
    ("sha256(counter)", lambda n: ctl_hash_counter(n),               "PASS all, H~1.0"),
]


def s22_calibration(n, reps=10, alpha=0.01, level=1e-3):
    """Check that SP 800-22 has the right FALSE-POSITIVE RATE on true randomness.

    The naive check "urandom must pass all 9 tests" is wrong, and it was in this
    file until it flaked. Each test rejects genuinely random data with
    probability alpha by construction, so with T tests the chance of at least one
    failure is 1-(1-alpha)^T - about 9% for T=9 at alpha=0.01. A check that
    demands a clean sweep therefore fails one run in eleven on a perfect source,
    which tells you nothing about the tooling and trains you to ignore it.

    What we want instead is whether the failure count over many independent
    random samples is consistent with alpha. The bar comes from the EXACT
    binomial tail, not from mean + 3*sigma: with R*T around 90 tests and
    alpha = 0.01 the mean is under 1, where the binomial is strongly
    right-skewed and the normal approximation gives a bar that is simultaneously
    too tight in one tail and too loose in the other. The 3-sigma version of this
    check also flaked, at 3 failures out of 45, which is a 1% event.

    Advisory results are excluded. A test below its recommended length is known to
    over-reject (see RECOMMENDED_N), so counting it here would fold a documented
    regime limit into a number that is supposed to measure implementation quality.

    Returns (failures, total, allowance, ok, pvals).
    """
    failures = 0
    total = 0
    pvals = []
    for _ in range(reps):
        for r in s22.run_all(ctl_urandom(n), alpha=alpha, fast=True):
            if r.skipped or r.advisory:
                continue
            total += 1
            pvals.append(r.p_value)
            if not r.passed:
                failures += 1
    allowance = specfun.binom_allowance(total, alpha, level=level)
    return failures, total, allowance, failures <= allowance, pvals


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    expected = s90.ideal_collision_hmin(n)
    bar = s90.ideal_collision_hmin(n, sigmas=4)
    mcv_bar = s90.ideal_mcv_hmin(n, sigmas=4)
    print("=" * 78)
    print(f"TOOLCHAIN VALIDATION  -  {n} bits per control stream")
    print("=" * 78)
    print("  Finite-sample ceilings at this length. An IDEAL binary source does")
    print("  NOT score 1.0, so good controls are checked against these, not 1.0:")
    print(f"    collision estimator : expected {expected:.4f}, 4-sigma bar {bar:.4f}")
    print(f"    most common value   : expected {s90.ideal_mcv_hmin(n):.4f}, "
          f"4-sigma bar {mcv_bar:.4f}")
    summary = []
    for name, gen, expect in CONTROLS:
        bits = gen(n)
        t0 = time.time()
        r22 = s22.run_all(bits, fast=True)
        npass, nfail, nadv, nskip = s22.tally(r22)
        # Full estimator set, not the fast subset. The fast subset omits t-Tuple,
        # LRS, MultiMMC and LZ78Y - which are precisely the estimators that catch
        # a medium-period sequence like lfsr8. Validating with the fast subset and
        # then asserting "lfsr8 is caught" tests the wrong thing.
        r90 = s90.run_all(bits, fast=False)
        h = s90.min_entropy(r90)
        dt = time.time() - t0
        print(f"\n--- {name}   (expect: {expect}) ---")
        print(f"    SP 800-22 : {npass} passed, {nfail} failed"
              f" ({nadv} advisory, {nskip} skipped)")
        for r in r22:
            if r.counts_as_failure:
                print(f"                FAIL {r.name} p={r.p_value:.2e}")
            elif r.advisory:
                print(f"                advisory-only {r.name} p={r.p_value:.2e}"
                      f" ({r.advisory_reason})")
        print(f"    SP 800-90B: H_min = {h:.6f} bits/bit   [{dt:.1f}s]")
        for e in r90:
            if e.min_entropy == e.min_entropy:
                print(f"                {e.name:<32} {e.min_entropy:8.6f}")
            else:
                print(f"                {e.name:<32}      n/a   {e.detail}")
        summary.append((name, npass, nfail, h, expect, r90))

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  {'control':<18}{'s22 pass':>10}{'fail':>6}{'H_min':>12}   expected")
    for name, npass, nfail, h, expect, _ in summary:
        print(f"  {name:<18}{npass:>10}{nfail:>6}{h:>12.6f}   {expect}")

    print("\n" + "=" * 78)
    print("SP 800-22 FALSE-POSITIVE CALIBRATION  (5 fresh urandom streams)")
    print("=" * 78)
    fails, tot, allow, cal_ok, pvals = s22_calibration(n)
    pvals_sorted = sorted(pvals)
    print(f"  {fails} failures out of {tot} tests at alpha=0.01 "
          f"(expected {0.01*tot:.2f}, exact-binomial allowance {allow})")
    print(f"  p-value spread: min={pvals_sorted[0]:.4f} "
          f"median={pvals_sorted[len(pvals_sorted)//2]:.4f} "
          f"max={pvals_sorted[-1]:.4f}")

    # ---- assertions ----
    # Two different kinds of check, for two different reasons.
    #
    # (1) EXACT estimators are checked against their analytic values. Most Common
    #     Value on an IID biased source has a closed-form answer, so this is a
    #     real correctness test of the arithmetic.
    #
    # (2) The reported MINIMUM over ten estimators is checked one-sided only. The
    #     non-IID estimators are deliberately conservative and several of them
    #     land well below the true value on a biased IID source - t-Tuple returns
    #     ~0.42 where the truth is 0.5146, because it takes the t-th root of a
    #     maximum order statistic, which is biased upward in p. That is intended
    #     behaviour, not error. The property that actually matters for safety is
    #     that the suite must never report MORE entropy than the source has;
    #     reporting less is conservative and acceptable.
    print("\n" + "=" * 78)
    print("CHECKS")
    print("=" * 78)
    d = {name: (npass, nfail, h, r90) for name, npass, nfail, h, _, r90 in summary}

    def mcv(name):
        return s90.get(d[name][3], "Most Common Value").min_entropy

    checks = [
        # (1) exact-estimator correctness against closed-form answers
        ("MCV on biased 0.70 within 0.05 of 0.5146",
         abs(mcv("biased p=0.70") - 0.5146) < 0.05),
        ("MCV on biased 0.90 within 0.05 of 0.1520",
         abs(mcv("biased p=0.90") - 0.1520) < 0.05),
        (f"MCV on urandom >= {mcv_bar:.4f} (4-sigma ideal-source bar, not 1.0)",
         mcv("urandom") >= mcv_bar),
        # (2) one-sided safety: never overstate the entropy of a known source
        ("biased 0.70 does NOT overstate (H_min <= 0.5146+0.03)",
         d["biased p=0.70"][2] <= 0.5146 + 0.03),
        ("biased 0.90 does NOT overstate (H_min <= 0.1520+0.03)",
         d["biased p=0.90"][2] <= 0.1520 + 0.03),
        ("biased 0.70 not absurdly pessimistic (H_min >= 0.25)",
         d["biased p=0.70"][2] >= 0.25),
        # (3) bad sources must be caught
        ("alternating H_min < 0.05",          d["alternating"][2] < 0.05),
        ("lfsr8 CAUGHT (H_min < 0.05)",       d["lfsr8 (p=255)"][2] < 0.05),
        ("lfsr8 also fails s22 (>=1 quotable failure)",
         d["lfsr8 (p=255)"][1] >= 1),
        # (4) good sources must clear the finite-sample bar, and must not collect
        #     any QUOTABLE s22 failure - advisory rows are excluded, which is the
        #     whole point of the advisory state
        (f"urandom H_min >= {bar:.4f}",        d["urandom"][2] >= bar),
        (f"s22 false-positive rate consistent with alpha ({fails}/{tot} <= {allow})",
         cal_ok),
        (f"sha256(counter) H_min >= {bar:.4f}", d["sha256(counter)"][2] >= bar),
        # (5) documented blind spot, asserted on purpose so it is a known
        #     property of the toolchain rather than a surprise in a report
        (f"lfsr32 NOT caught (H_min >= {bar:.4f}) - known theoretical limit",
         d["lfsr32"][2] >= bar),
    ]
    ok = True
    for label, cond in checks:
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
        ok &= cond
    print()
    print("  Note on the last check: lfsr32 and sha256(counter) both have ZERO")
    print("  entropy and both score as high as true randomness. Passing these")
    print("  suites is therefore not an entropy claim - it only rules out")
    print("  structure short enough to be visible in the sample. lfsr8 (period")
    print("  255) is short enough; lfsr32 is not. Entropy claims rest on a")
    print("  physical argument about the source.")
    print()
    print("  And 'visible in the sample' is narrower than it sounds. Measured at")
    print("  n=20000, only 2 of the 10 estimators catch lfsr8 at all - MultiMMC")
    print("  and LZ78Y. The other 8 miss it, and the Lag predictor at the D=128")
    print("  that SP 800-90B mandates returns the MAXIMUM 1.000000 for it, since")
    print("  a period of 255 is longer than any lag it can express. So the margin")
    print("  by which this control is caught is two estimators wide, which is why")
    print("  the 90B side above is deliberately run with fast=False.")
    print()
    if ok:
        print("  RESULT: TOOLCHAIN VALIDATED - estimators behave correctly on known inputs")
    else:
        print("  RESULT: VALIDATION FAILED - do not quote numbers from this toolchain yet")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
