"""
Calibration of the SP 800-22 implementation: are the p-values actually uniform?

Why this is a separate, stronger check than validate_toolchain.py
----------------------------------------------------------------
validate_toolchain.py asks "does the suite catch bad sources and pass good
ones?". That is necessary but weak - a test that returned p = 0.5 for every
input would pass several of those checks.

The defining property of a correctly implemented statistical test is that on
genuinely random input its p-value is UNIFORM on [0, 1]. That single property
implies the false-positive rate equals alpha, and it is sensitive to arithmetic
errors that a pass/fail check sails past: a wrong degrees-of-freedom, a
mis-scaled chi-square, a sign error in a normal CDF tail all distort the p-value
distribution while still "passing random data".

So this script runs the suite over many independent os.urandom streams and
applies a Kolmogorov-Smirnov test for uniformity to each test's p-values.

How to read the output
----------------------
"ok"                   KS statistic below the 1% critical value; the test's
                       p-value distribution is indistinguishable from uniform.
                       This is the result you want for a single-p test.

"conservative/skewed"  Mean p well above 0.5 and a large KS statistic. Expected,
                       and acceptable, for the tests marked [k sub-tests]: their
                       reported p is the Bonferroni family value min(1, k*p_min),
                       which is conservative when the sub-tests are correlated.
                       Conservative means it errs toward declaring data random,
                       so it cannot manufacture a false accusation against a
                       source - but it does cost sensitivity.

"NOT UNIFORM (low)"    Mean p below 0.5 with a large KS statistic. This is the
                       dangerous direction and indicates a real bug: the test
                       over-rejects, so it will accuse a good source of being
                       non-random. Do not report results until it is fixed.

This script found exactly that on its first run. Non-overlapping Template,
Serial and Cumulative Sums were reporting a raw minimum over sub-tests as though
it were a p-value; the Non-overlapping Template figure had median 0.040 and fell
below alpha in 28% of runs on perfect data. See _family_p in nist_sp800_22.py.

A note on this script's own correctness
---------------------------------------
It then made the same mistake itself. Comparing each test's KS statistic against
a single 1% critical value means running T independent tests at the 1% level, so
the chance that at least one trips on flawless data is 1-(1-0.01)^T - about 9%
for T=9. The script duly reported "Approximate entropy NOT UNIFORM (low)" on one
run; a 500-replicate follow-up at the same m put it at mean_p 0.4857, KS 0.0425
against a 1% critical value of 0.0729, and a p<0.01 rate of 0.0080. Perfectly
clean. The alarm was the script, not the test.

So the KS statistics are now converted to KS p-values and Bonferroni-corrected
across however many tests actually ran. Two consequences worth stating plainly:
a raw statistic cannot be multiplicity-corrected while a p-value can, which is
the practical reason to always carry p-values around; and a tool built to catch
a class of error is not thereby immune to it.

Usage:  python3 calibrate_s22.py [reps] [bits_per_rep]
"""

import collections
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nist_sp800_22 as s22
import specfun

ALPHA = 0.01          # the suite's own significance level
KS_ALPHA = 0.01       # family-wise level for the uniformity checks below


def urandom_bits(n):
    out = []
    for byte in os.urandom(n // 8 + 1):
        for k in range(7, -1, -1):
            out.append((byte >> k) & 1)
            if len(out) == n:
                return out
    return out


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20000

    pvals = collections.defaultdict(list)
    fails = collections.Counter()
    subtests = {}
    advisory = {}
    for _ in range(reps):
        for r in s22.run_all(urandom_bits(n), alpha=ALPHA, fast=True):
            if r.skipped:
                continue
            pvals[r.name].append(r.p_value)
            subtests[r.name] = r.subtests or 1
            advisory[r.name] = r.advisory
            if not r.passed:
                fails[r.name] += 1

    T = len(pvals)
    ks_thresh = KS_ALPHA / T if T else KS_ALPHA
    print("=" * 94)
    print(f"SP 800-22 CALIBRATION  -  {reps} independent urandom streams of {n} bits")
    print("=" * 94)
    print("  A correct test yields uniform p-values on random input.")
    print(f"  {T} tests ran, so uniformity is judged at the Bonferroni-corrected")
    print(f"  level {KS_ALPHA}/{T} = {ks_thresh:.2e}. Judging each at {KS_ALPHA} instead would")
    print(f"  false-alarm on {100*(1-(1-KS_ALPHA)**T):.0f}% of runs on a perfect source.")
    print()
    print(f"  {'test':<28}{'sub':>4}{'mean_p':>8}{'KS':>8}{'KS p':>9}"
          f"{'fail%':>7}  verdict")

    tot_f = tot_r = 0
    bad = []
    for name, arr in pvals.items():
        d = specfun.ks_statistic(arr)
        ks_p = specfun.ks_pvalue(d, len(arr))
        mean_p = sum(arr) / len(arr)
        k = subtests[name]
        adv = advisory[name]
        # Advisory tests are out of their length regime by construction, so their
        # non-uniformity is expected and is not evidence of a coding error. They
        # are excluded from the overall false-positive rate for the same reason.
        if not adv:
            tot_f += fails[name]
            tot_r += len(arr)
        if adv:
            verdict = "ADVISORY (out of length regime) - excluded"
        elif ks_p >= ks_thresh:
            verdict = "ok"
        elif mean_p > 0.5:
            verdict = "conservative/skewed (expected for family p)"
        else:
            verdict = "NOT UNIFORM (low) - OVER-REJECTS, BUG"
            bad.append(name)
        print(f"  {name:<28}{k:>4}{mean_p:>8.3f}{d:>8.4f}{ks_p:>9.4f}"
              f"{100*fails[name]/len(arr):>7.1f}  {verdict}")

    allow = specfun.binom_allowance(tot_r, ALPHA, level=1e-3)
    rate_ok = tot_f <= allow
    print()
    print(f"  Overall false-positive rate: {tot_f}/{tot_r} = {100*tot_f/tot_r:.2f}% "
          f"(nominal {100*ALPHA:.2f}%, exact-binomial allowance {allow})")
    print("  Advisory tests are excluded from that count - see the note above.")
    print()
    if bad:
        print("  RESULT: CALIBRATION FAILED - these tests over-reject random data:")
        for b in bad:
            print(f"          {b}")
        print("  Any 'FAIL' they report on real data may be the test, not the source.")
        return 1
    if not rate_ok:
        print("  RESULT: CALIBRATION FAILED - overall rejection rate exceeds allowance")
        return 1
    print("  RESULT: CALIBRATED - no test over-rejects; skew is conservative only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
