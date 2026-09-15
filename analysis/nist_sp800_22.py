"""
NIST SP 800-22 statistical test suite for random and pseudorandom number
generators, implemented from the published specification (Rev 1a).

Design notes
------------
* Pure Python + optional numpy. numpy is used only to accelerate the DFT in the
  spectral test; without it the test truncates to a power-of-two length and says
  so in its details field, rather than silently changing the statistic.
* Every test reports why it was skipped when the input is too short, instead of
  returning a misleading pass. A skipped test is not a passed test.
* IMPORTANT INTERPRETIVE NOTE. This suite answers "is this stream statistically
  distinguishable from random?" A cryptographic PRNG, a hash output, and an
  AES-conditioned counter all pass every test here. Passing therefore does NOT
  establish that a source produces entropy. For that, use sp800_90b.py, which
  includes the predictor-based estimators that catch structure this suite is
  blind to by construction.

Usage:
    from nist_sp800_22 import run_all
    results = run_all(bits)          # bits: sequence of 0/1 ints
"""

import math
from specfun import (igamc, normal_cdf, berlekamp_massey, gf2_rank,
                     aperiodic_templates)

try:
    import numpy as _np
except ImportError:
    _np = None

DEFAULT_ALPHA = 0.01


# ----------------------------------------------------------------------------
# length regime
# ----------------------------------------------------------------------------
#
# Every p-value here comes from an ASYMPTOTIC reference distribution. Below a
# certain length the statistic is still computable and its bulk distribution is
# still roughly right, but its far tail is not - and the far tail is exactly
# where a verdict lives. A test run below its regime does not fail loudly, it
# fails quietly by rejecting good data.
#
# This was measured, not assumed. Over independent os.urandom streams, using all
# 148 aperiodic templates, the per-template p-values of the non-overlapping
# template test behaved like this (mu = (M-m+1)/2^m is the expected match count
# per block; ratios are observed rate / nominal rate, so 1.00x is correct):
#
#     n          mu     P(p<0.1)  P(p<0.01)  P(p<0.001)   KS p    family reject
#     20,000     4.9      0.98x     1.41x      2.56x      0.0000    4.3 - 6.5%
#  1,000,000   244.1      1.00x     1.01x      1.01x      0.6929    1.15% +-0.81%
#
# The second row is the important one. At the length SP 800-22 actually specifies,
# this implementation is correct to within 0.2 sigma on every tail probability,
# and the Bonferroni family rejection rate matches alpha. So the short-n misbehaviour
# is NOT a coding error - it is the chi-square reference distribution being asked
# for a far-tail probability at mu = 4.9, where the per-block counts are small
# integers and the asymptotic approximation has not converged. Diagnosing which of
# those two it was mattered: a bug must be fixed, a regime limit must be respected.
#
# (The n=20,000 significances survive the fact that sub-tests on one stream are
# correlated. Computing the per-stream fraction and taking its across-rep standard
# error - which assumes no independence between templates - the 1.41x is +9.45
# sigma and the 2.56x is +8.45 sigma. Correlation inflates the spread by only
# 1.29x. Note also that P(p<0.1) is slightly BELOW nominal while the far tail is
# far above: mass is displaced toward zero from just above it, which is the
# signature of discreteness, not of a scaling error.)
#
# Four different ways of combining the 148 sub-test p-values were then tried at
# n = 20,000 - Bonferroni min(1, k*p_min), NIST's own second-level 10-bin
# chi-square, Fisher's -2*sum(ln p), and a KS test of the row against U[0,1].
# All four over-rejected (6.5%, 2.8%, 3.2%, 4.0%). That is the useful finding:
# the defect is not in the combination rule, it is that the INPUTS are not
# uniform at this length, and no combining rule can repair non-uniform inputs.
# The only correct response is to respect the length requirement.
#
# Hence: tests below their recommended n are marked ADVISORY. Their p-value is
# still printed, because it is informative for engineering, but it cannot be
# counted as a failure and must not be quoted as evidence about a source.
RECOMMENDED_N = {
    "Frequency (monobit)":      (100,      "spec minimum"),
    "Block frequency":          (100,      "spec minimum"),
    "Runs":                     (100,      "spec minimum"),
    "Longest run of ones":      (6272,     "M=128 parameter set"),
    "Binary matrix rank":       (38912,    "38 matrices of 32x32"),
    "Spectral (DFT)":           (1000,     "spec minimum"),
    "Non-overlapping template": (1000000,  "measured: sub-test p far tail 4.5x "
                                           "too heavy at n=2e4, 2.5x at n=1e5"),
    "Overlapping template":     (1000000,  "needs N=968 blocks of M=1032"),
    "Maurer's universal":       (387840,   "smallest L=6 parameter set"),
    "Linear complexity":        (1000000,  "needs N>=200 blocks of M=500"),
    "Serial":                   (100,      "spec minimum"),
    "Approximate entropy":      (100,      "spec minimum"),
    "Cumulative sums":          (100,      "spec minimum"),
    "Random excursions":        (1000000,  "needs J>=500 zero-crossing cycles"),
    "Random excursions variant": (1000000, "needs J>=500 zero-crossing cycles"),
}


# ----------------------------------------------------------------------------
# result container
# ----------------------------------------------------------------------------

class Result:
    """One test's outcome. Note there are THREE verdict states, not two.

      skipped  = True   the statistic is not even defined at this length
                        (too few blocks, too few cycles). Not a pass.
      advisory = True   the statistic is defined and is reported, but n is below
                        the length at which its reference distribution is
                        trustworthy in the tail. A small p here is not evidence
                        against the source, so it is NOT counted as a failure.
      otherwise         a real PASS/FAIL against alpha.

    The advisory state exists because of a measured problem, not out of caution.
    See RECOMMENDED_N below.
    """

    __slots__ = ("name", "p_value", "passed", "skipped", "detail",
                 "subtests", "worst_p", "advisory", "advisory_reason")

    def __init__(self, name, p_value=None, skipped=None, detail="",
                 alpha=DEFAULT_ALPHA, passed=None, subtests=None, worst_p=None):
        self.name = name
        self.p_value = p_value
        self.skipped = skipped
        self.detail = detail
        self.subtests = subtests      # >1 for tests producing many p-values
        self.worst_p = worst_p        # raw minimum across sub-tests, if any
        self.advisory = False
        self.advisory_reason = ""
        if skipped is not None:
            self.passed = None
        elif passed is not None:
            self.passed = passed
        else:
            self.passed = (p_value >= alpha)

    @property
    def counts_as_failure(self):
        """A FAIL that may legitimately be quoted against the source."""
        return (not self.skipped) and (not self.advisory) and (not self.passed)

    def __repr__(self):
        if self.skipped:
            return f"<{self.name}: SKIPPED ({self.skipped})>"
        if self.advisory:
            return f"<{self.name}: p={self.p_value:.6f} ADVISORY>"
        return f"<{self.name}: p={self.p_value:.6f} {'PASS' if self.passed else 'FAIL'}>"


def _family_p(p_min, k):
    """Family-wise p-value from the smallest of k sub-test p-values (Bonferroni).

    Five of these tests produce more than one p-value: Serial and Cumulative Sums
    produce two each by construction, and Non-overlapping Template, Random
    Excursions and Random Excursions Variant produce one per template or per
    excursion state. Reporting min(p) in a column headed "p" is wrong and it is
    actively misleading in a write-up, because the minimum of k uniforms is not
    uniform - its median is about ln(2)/k. Measured over 200 random streams, the
    raw minimum for Non-overlapping Template had median 0.040 and fell below 0.01
    in 28% of runs on perfectly good data. Anyone comparing that number against
    0.01 would conclude the source was broken.

    min(1, k * p_min) is a valid p-value for the family by the union bound, so it
    IS comparable against alpha and against the single-p tests. It is
    conservative when the sub-tests are correlated (forward and backward CUSUM
    especially), which errs toward declaring randomness - so it must not be the
    sole verdict for the many-sub-test cases. See _multi_verdict.
    """
    if k is None or k <= 1:
        return p_min
    return min(1.0, k * p_min)


def _multi_allowance(total, alpha=DEFAULT_ALPHA):
    """How many sub-test failures are unremarkable by chance, for the DETAIL text.

    This used to be the verdict for the many-sub-test tests, via a
    proportion-of-sub-tests-failing criterion with a 3-sigma binomial margin.
    Calibration showed that over-rejects: Non-overlapping Template rejected 4.0%
    of genuinely random streams where the independent-binomial calculation
    predicts 1.7%. The cause is that sub-tests computed over the SAME data are
    positively correlated - a stream that happens to have unusual block structure
    pushes several templates off at once - so the true variance of the failure
    count exceeds the binomial variance and a binomial margin is too tight.

    The verdict is now the Bonferroni family p-value instead, which is valid
    under arbitrary dependence between sub-tests and therefore holds the
    false-positive rate at or below alpha no matter how correlated they are. The
    cost is sensitivity, and that is an acceptable trade here: SP 800-22 is not
    where an entropy claim comes from (a counter through SHA-256 passes all of
    it), so its job is to characterise the digital datapath without manufacturing
    false accusations. Sensitivity against structure is supplied by the SP 800-90B
    predictors, which is the right instrument for it.

    This function is retained because the raw failure count is informative in a
    report - it distinguishes "one template was unlucky" from "forty templates
    all deviated" even when both give the same family p.
    """
    expected = alpha * total
    margin = 3.0 * math.sqrt(total * alpha * (1.0 - alpha))
    return max(1.0, expected + margin)


def _pm1(bits):
    return [2 * b - 1 for b in bits]


# ----------------------------------------------------------------------------
# 1. Frequency (monobit)
# ----------------------------------------------------------------------------

def frequency(bits, alpha=DEFAULT_ALPHA):
    n = len(bits)
    if n < 100:
        return Result("Frequency (monobit)", skipped=f"n={n} < 100")
    s = abs(sum(_pm1(bits))) / math.sqrt(n)
    p = math.erfc(s / math.sqrt(2))
    ones = sum(bits)
    return Result("Frequency (monobit)", p, detail=f"ones={ones} P(1)={ones/n:.6f}", alpha=alpha)


# ----------------------------------------------------------------------------
# 2. Frequency within a block
# ----------------------------------------------------------------------------

def block_frequency(bits, M=128, alpha=DEFAULT_ALPHA):
    n = len(bits)
    if n < 100:
        return Result("Block frequency", skipped=f"n={n} < 100")
    if M < 20 or M <= 0.01 * n:
        M = max(20, int(0.02 * n))
    N = n // M
    if N < 1:
        return Result("Block frequency", skipped=f"n={n} too short for M={M}")
    if N > 100:
        M = n // 100
        N = n // M
    chi2 = 0.0
    for i in range(N):
        pi = sum(bits[i * M:(i + 1) * M]) / M
        chi2 += (pi - 0.5) ** 2
    chi2 *= 4.0 * M
    p = igamc(N / 2.0, chi2 / 2.0)
    return Result("Block frequency", p, detail=f"M={M} N={N} chi2={chi2:.3f}", alpha=alpha)


# ----------------------------------------------------------------------------
# 3. Runs
# ----------------------------------------------------------------------------

def runs(bits, alpha=DEFAULT_ALPHA):
    n = len(bits)
    if n < 100:
        return Result("Runs", skipped=f"n={n} < 100")
    pi = sum(bits) / n
    if abs(pi - 0.5) >= 2.0 / math.sqrt(n):
        return Result("Runs", 0.0,
                      detail=f"prerequisite failed: |P(1)-0.5|={abs(pi-0.5):.6f} "
                             f">= 2/sqrt(n)={2/math.sqrt(n):.6f}", alpha=alpha)
    v = 1 + sum(1 for i in range(1, n) if bits[i] != bits[i - 1])
    num = abs(v - 2.0 * n * pi * (1 - pi))
    den = 2.0 * math.sqrt(2.0 * n) * pi * (1 - pi)
    p = math.erfc(num / den)
    return Result("Runs", p, detail=f"runs={v} expected={2*n*pi*(1-pi):.1f}", alpha=alpha)


# ----------------------------------------------------------------------------
# 4. Longest run of ones in a block
# ----------------------------------------------------------------------------

_LONGEST_RUN_PARAMS = [
    # (min_n, M, K, first_class, pi)
    (750000, 10000, 6, 10, [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]),
    (6272, 128, 5, 4, [0.1174035788, 0.242955959, 0.249363483,
                       0.17517706, 0.102701071, 0.112446329]),
    (128, 8, 3, 1, [0.2148, 0.3672, 0.2305, 0.1875]),
]


def longest_run_of_ones(bits, alpha=DEFAULT_ALPHA):
    n = len(bits)
    params = None
    for min_n, M, K, first, pi in _LONGEST_RUN_PARAMS:
        if n >= min_n:
            params = (M, K, first, pi)
            break
    if params is None:
        return Result("Longest run of ones", skipped=f"n={n} < 128")
    M, K, first, pi = params
    N = n // M
    counts = [0] * (K + 1)
    for i in range(N):
        block = bits[i * M:(i + 1) * M]
        longest = cur = 0
        for b in block:
            if b:
                cur += 1
                if cur > longest:
                    longest = cur
            else:
                cur = 0
        idx = min(max(longest - first, 0), K)
        counts[idx] += 1
    chi2 = sum((counts[i] - N * pi[i]) ** 2 / (N * pi[i]) for i in range(K + 1))
    p = igamc(K / 2.0, chi2 / 2.0)
    return Result("Longest run of ones", p,
                  detail=f"M={M} N={N} classes={counts} chi2={chi2:.3f}", alpha=alpha)


# ----------------------------------------------------------------------------
# 5. Binary matrix rank
# ----------------------------------------------------------------------------

def binary_matrix_rank(bits, M=32, Q=32, alpha=DEFAULT_ALPHA):
    n = len(bits)
    N = n // (M * Q)
    if N < 38:
        return Result("Binary matrix rank",
                      skipped=f"needs n >= {38*M*Q} for {M}x{Q} matrices, have n={n} (N={N})")
    full = 0
    full_minus_1 = 0
    for k in range(N):
        base = k * M * Q
        rows = []
        for r in range(M):
            val = 0
            off = base + r * Q
            for c in range(Q):
                if bits[off + c]:
                    val |= (1 << c)
            rows.append(val)
        rk = gf2_rank(rows, Q)
        if rk == M:
            full += 1
        elif rk == M - 1:
            full_minus_1 += 1
    rest = N - full - full_minus_1
    chi2 = ((full - 0.2888 * N) ** 2 / (0.2888 * N)
            + (full_minus_1 - 0.5776 * N) ** 2 / (0.5776 * N)
            + (rest - 0.1336 * N) ** 2 / (0.1336 * N))
    p = math.exp(-chi2 / 2.0)
    return Result("Binary matrix rank", p,
                  detail=f"N={N} full={full} full-1={full_minus_1} lower={rest}", alpha=alpha)


# ----------------------------------------------------------------------------
# 6. Discrete Fourier transform (spectral)
# ----------------------------------------------------------------------------

def _fft_pow2(x):
    """Iterative radix-2 Cooley-Tukey, used only when numpy is unavailable."""
    n = len(x)
    j = 0
    x = list(x)
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            x[i], x[j] = x[j], x[i]
    length = 2
    while length <= n:
        ang = -2j * math.pi / length
        wl = complex(math.cos(ang.imag), math.sin(ang.imag))
        for i in range(0, n, length):
            w = 1 + 0j
            half = length >> 1
            for k in range(i, i + half):
                u = x[k]
                v = x[k + half] * w
                x[k] = u + v
                x[k + half] = u - v
                w *= wl
        length <<= 1
    return x


def spectral(bits, alpha=DEFAULT_ALPHA):
    n = len(bits)
    if n < 1000:
        return Result("Spectral (DFT)", skipped=f"n={n} < 1000")
    note = ""
    x = _pm1(bits)
    if _np is not None:
        mag = abs(_np.fft.rfft(_np.asarray(x, dtype=float))[1:n // 2 + 1])
        m = mag[:n // 2]
        n_eff = n
    else:
        n_eff = 1 << (n.bit_length() - 1)
        if n_eff != n:
            note = f" (numpy absent: truncated {n} -> {n_eff} for radix-2 FFT)"
        spec = _fft_pow2([complex(v, 0.0) for v in x[:n_eff]])
        m = [abs(spec[i]) for i in range(1, n_eff // 2 + 1)][:n_eff // 2]
    T = math.sqrt(math.log(1.0 / 0.05) * n_eff)
    n0 = 0.95 * n_eff / 2.0
    n1 = sum(1 for v in m if v < T)
    d = (n1 - n0) / math.sqrt(n_eff * 0.95 * 0.05 / 4.0)
    p = math.erfc(abs(d) / math.sqrt(2))
    return Result("Spectral (DFT)", p,
                  detail=f"peaks below T: {n1} expected {n0:.1f}{note}", alpha=alpha)


# ----------------------------------------------------------------------------
# 7. Non-overlapping template matching
# ----------------------------------------------------------------------------

def non_overlapping_template(bits, m=9, N=8, alpha=DEFAULT_ALPHA, max_templates=None):
    """NIST 2.7. One chi-square per aperiodic m-bit template, over N blocks.

    max_templates exists for experiments only and should normally be left None.
    Truncating the template set does not merely make the test cheaper, it makes it
    a DIFFERENT test: k changes, so the family p-value changes, and the retained
    subset is not statistically representative. Measured at n=20,000, the first 20
    templates in enumeration order gave P(sub-p < 0.01) = 0.0104 while the full
    148 gave 0.0141 - so truncation was accidentally hiding the tail problem that
    RECOMMENDED_N now documents. Since the scan moved to str.count, all 148
    templates cost about 0.13 s at n = 1e5, so there is no reason to truncate.
    """
    n = len(bits)
    M = n // N
    if M < m + 1:
        return Result("Non-overlapping template", skipped=f"n={n} too short for m={m}, N={N}")
    templates = aperiodic_templates(m)
    if max_templates:
        templates = templates[:max_templates]
    mu = (M - m + 1) / (2 ** m)
    var = M * (1.0 / (2 ** m) - (2.0 * m - 1.0) / (2 ** (2 * m)))
    if var <= 0:
        return Result("Non-overlapping template", skipped="degenerate variance")
    # str.count counts NON-OVERLAPPING occurrences left to right, advancing past
    # each match - which is exactly NIST's scan rule (advance by m on a hit, by 1
    # otherwise). Doing it in C rather than a Python loop is a ~100x speedup, and
    # it is what makes calibrating this test at n >= 1e5 feasible at all.
    s = ''.join('1' if b else '0' for b in bits)
    blocks = [s[j * M:(j + 1) * M] for j in range(N)]
    worst_p = 1.0
    worst_t = None
    fails = 0
    for tmpl in templates:
        ts = ''.join('1' if b else '0' for b in tmpl)
        chi2 = 0.0
        for blk in blocks:
            w = blk.count(ts)
            chi2 += (w - mu) ** 2 / var
        p = igamc(N / 2.0, chi2 / 2.0)
        if p < alpha:
            fails += 1
        if p < worst_p:
            worst_p = p
            worst_t = tmpl
    ts = ''.join(str(b) for b in worst_t) if worst_t else "?"
    k = len(templates)
    return Result("Non-overlapping template", _family_p(worst_p, k),
                  detail=f"m={m} N={N} {k} templates, "
                         f"{fails} below alpha (chance allows ~"
                         f"{_multi_allowance(k, alpha):.1f})"
                         f"; worst template={ts} raw min p={worst_p:.3e}",
                  alpha=alpha, subtests=k, worst_p=worst_p)


# ----------------------------------------------------------------------------
# 8. Overlapping template matching
# ----------------------------------------------------------------------------

_OVERLAP_PI = [0.364091, 0.185659, 0.139381, 0.100571, 0.070432, 0.139865]


def overlapping_template(bits, m=9, M=1032, alpha=DEFAULT_ALPHA):
    n = len(bits)
    N = n // M
    if N < 20:
        return Result("Overlapping template",
                      skipped=f"needs n >= {20*M} for M={M}, have n={n} (N={N})")
    note = "" if N >= 968 else f" (N={N} below NIST's recommended 968)"
    K = 5
    counts = [0] * (K + 1)
    # This test counts OVERLAPPING occurrences of m ones, so str.count (which is
    # non-overlapping) cannot be used as it is in the non-overlapping test. But a
    # maximal run of L consecutive ones contains exactly L-m+1 overlapping
    # matches when L >= m, so splitting on zeros gives the same count at C speed.
    # The obvious triple loop is O(M*m) per block in Python and dominates the
    # whole suite's runtime at n = 1e6.
    s = ''.join('1' if b else '0' for b in bits)
    for j in range(N):
        blk = s[j * M:(j + 1) * M]
        w = sum(len(run) - m + 1 for run in blk.split('0') if len(run) >= m)
        counts[min(w, K)] += 1
    chi2 = sum((counts[i] - N * _OVERLAP_PI[i]) ** 2 / (N * _OVERLAP_PI[i])
               for i in range(K + 1))
    p = igamc(K / 2.0, chi2 / 2.0)
    return Result("Overlapping template", p,
                  detail=f"m={m} M={M} N={N} classes={counts}{note}", alpha=alpha)


# ----------------------------------------------------------------------------
# 9. Maurer's universal statistical test
# ----------------------------------------------------------------------------

_UNIV_THRESH = [(387840, 6), (904960, 7), (2068480, 8), (4654080, 9),
                (10342400, 10), (22753280, 11), (49643520, 12),
                (107560960, 13), (231669760, 14), (496435200, 15),
                (1059061760, 16)]
_UNIV_EXPECTED = {6: 5.2177052, 7: 6.1962507, 8: 7.1836656, 9: 8.1764248,
                  10: 9.1723243, 11: 10.170032, 12: 11.168765, 13: 12.168070,
                  14: 13.167693, 15: 14.167488, 16: 15.167379}
_UNIV_VARIANCE = {6: 2.954, 7: 3.125, 8: 3.238, 9: 3.311, 10: 3.356, 11: 3.384,
                  12: 3.401, 13: 3.410, 14: 3.416, 15: 3.419, 16: 3.421}


def universal(bits, alpha=DEFAULT_ALPHA):
    n = len(bits)
    L = None
    for min_n, cand in _UNIV_THRESH:
        if n >= min_n:
            L = cand
    if L is None:
        return Result("Maurer's universal", skipped=f"needs n >= 387840, have n={n}")
    Q = 10 * (2 ** L)
    K = n // L - Q
    table = [0] * (2 ** L)
    for i in range(Q):
        blk = 0
        for b in bits[i * L:(i + 1) * L]:
            blk = (blk << 1) | b
        table[blk] = i + 1
    total = 0.0
    for i in range(Q, Q + K):
        blk = 0
        for b in bits[i * L:(i + 1) * L]:
            blk = (blk << 1) | b
        total += math.log((i + 1) - table[blk], 2)
        table[blk] = i + 1
    fn = total / K
    c = 0.7 - 0.8 / L + (4.0 + 32.0 / L) * (K ** (-3.0 / L)) / 15.0
    sigma = c * math.sqrt(_UNIV_VARIANCE[L] / K)
    p = math.erfc(abs((fn - _UNIV_EXPECTED[L]) / (math.sqrt(2) * sigma)))
    return Result("Maurer's universal", p,
                  detail=f"L={L} Q={Q} K={K} fn={fn:.6f} expected={_UNIV_EXPECTED[L]}",
                  alpha=alpha)


# ----------------------------------------------------------------------------
# 10. Linear complexity
# ----------------------------------------------------------------------------

_LC_PI = [0.010417, 0.03125, 0.125, 0.5, 0.25, 0.0625, 0.020833]


def linear_complexity(bits, M=500, alpha=DEFAULT_ALPHA):
    n = len(bits)
    N = n // M
    if N < 200:
        return Result("Linear complexity",
                      skipped=f"needs n >= {200*M} for M={M}, have n={n} (N={N})")
    mu = (M / 2.0 + (9.0 + (-1) ** (M + 1)) / 36.0
          - (M / 3.0 + 2.0 / 9.0) / (2 ** M))
    counts = [0] * 7
    lcs = []
    for i in range(N):
        L = berlekamp_massey(bits[i * M:(i + 1) * M])
        lcs.append(L)
        T = ((-1) ** M) * (L - mu) + 2.0 / 9.0
        if T <= -2.5:
            counts[0] += 1
        elif T <= -1.5:
            counts[1] += 1
        elif T <= -0.5:
            counts[2] += 1
        elif T <= 0.5:
            counts[3] += 1
        elif T <= 1.5:
            counts[4] += 1
        elif T <= 2.5:
            counts[5] += 1
        else:
            counts[6] += 1
    chi2 = sum((counts[i] - N * _LC_PI[i]) ** 2 / (N * _LC_PI[i]) for i in range(7))
    p = igamc(6 / 2.0, chi2 / 2.0)
    mean_lc = sum(lcs) / len(lcs)
    return Result("Linear complexity", p,
                  detail=f"M={M} N={N} mean L={mean_lc:.1f} (ideal ~{mu:.1f}) "
                         f"classes={counts}", alpha=alpha)


# ----------------------------------------------------------------------------
# 11. Serial
# ----------------------------------------------------------------------------

def _psi2(bits, m, n):
    if m <= 0:
        return 0.0
    ext = bits + bits[:m - 1]
    counts = {}
    for i in range(n):
        key = 0
        for k in range(m):
            key = (key << 1) | ext[i + k]
        counts[key] = counts.get(key, 0) + 1
    return (2 ** m) / n * sum(v * v for v in counts.values()) - n


def serial(bits, m=None, alpha=DEFAULT_ALPHA):
    n = len(bits)
    if n < 100:
        return Result("Serial", skipped=f"n={n} < 100")
    if m is None:
        m = min(16, int(math.log2(n)) - 3)
    if m < 2:
        return Result("Serial", skipped=f"n={n} too short")
    p0 = _psi2(bits, m, n)
    p1 = _psi2(bits, m - 1, n)
    p2 = _psi2(bits, m - 2, n)
    d1 = p0 - p1
    d2 = p0 - 2 * p1 + p2
    pv1 = igamc(2 ** (m - 2), d1 / 2.0)
    pv2 = igamc(2 ** (m - 3), d2 / 2.0)
    p = min(pv1, pv2)
    return Result("Serial", _family_p(p, 2),
                  detail=f"m={m} p1={pv1:.6f} p2={pv2:.6f} (2 sub-tests, "
                         f"family p = 2*min)",
                  alpha=alpha, subtests=2, worst_p=p)


# ----------------------------------------------------------------------------
# 12. Approximate entropy
# ----------------------------------------------------------------------------

def approximate_entropy(bits, m=None, alpha=DEFAULT_ALPHA):
    n = len(bits)
    if n < 100:
        return Result("Approximate entropy", skipped=f"n={n} < 100")
    if m is None:
        m = max(2, min(10, int(math.log2(n)) - 6))

    def phi(mm):
        ext = bits + bits[:mm - 1] if mm > 1 else list(bits)
        counts = {}
        for i in range(n):
            key = 0
            for k in range(mm):
                key = (key << 1) | ext[i + k]
            counts[key] = counts.get(key, 0) + 1
        return sum((v / n) * math.log(v / n) for v in counts.values())

    apen = phi(m) - phi(m + 1)
    chi2 = 2.0 * n * (math.log(2) - apen)
    p = igamc(2 ** (m - 1), chi2 / 2.0)
    return Result("Approximate entropy", p,
                  detail=f"m={m} ApEn={apen:.6f} chi2={chi2:.3f}", alpha=alpha)


# ----------------------------------------------------------------------------
# 13. Cumulative sums (cusum)
# ----------------------------------------------------------------------------

def cumulative_sums(bits, alpha=DEFAULT_ALPHA):
    n = len(bits)
    if n < 100:
        return Result("Cumulative sums", skipped=f"n={n} < 100")
    x = _pm1(bits)

    def one(seq):
        s = 0
        z = 0
        for v in seq:
            s += v
            if abs(s) > z:
                z = abs(s)
        if z == 0:
            return 1.0
        sq = math.sqrt(n)
        total = 0.0
        k = int((-n / z + 1) // 4)
        kmax = int((n / z - 1) // 4)
        while k <= kmax:
            total += (normal_cdf((4 * k + 1) * z / sq)
                      - normal_cdf((4 * k - 1) * z / sq))
            k += 1
        sub = 0.0
        k = int((-n / z - 3) // 4)
        while k <= kmax:
            sub += (normal_cdf((4 * k + 3) * z / sq)
                    - normal_cdf((4 * k + 1) * z / sq))
            k += 1
        return max(0.0, min(1.0, 1.0 - total + sub))

    pf = one(x)
    pb = one(list(reversed(x)))
    return Result("Cumulative sums", _family_p(min(pf, pb), 2),
                  detail=f"forward={pf:.6f} backward={pb:.6f} (2 sub-tests, "
                         f"family p = 2*min)",
                  alpha=alpha, subtests=2, worst_p=min(pf, pb))


# ----------------------------------------------------------------------------
# 14 / 15. Random excursions and variant
# ----------------------------------------------------------------------------

def _cycles(bits):
    s = 0
    walk = []
    for b in bits:
        s += 2 * b - 1
        walk.append(s)
    cyc = []
    cur = []
    for v in walk:
        cur.append(v)
        if v == 0:
            cyc.append(cur)
            cur = []
    if cur:
        cyc.append(cur)
    return walk, cyc


def random_excursions(bits, alpha=DEFAULT_ALPHA):
    n = len(bits)
    walk, cyc = _cycles(bits)
    J = len(cyc)
    if J < 500:
        return Result("Random excursions",
                      skipped=f"needs >= 500 zero-crossing cycles, found {J}")
    worst = 1.0
    fails = 0
    for x in [-4, -3, -2, -1, 1, 2, 3, 4]:
        vk = [0] * 6
        for c in cyc:
            cnt = sum(1 for v in c if v == x)
            vk[min(cnt, 5)] += 1
        ax = abs(x)
        pi = [1.0 - 1.0 / (2.0 * ax)]
        for k in range(1, 5):
            pi.append((1.0 / (4.0 * x * x)) * (1.0 - 1.0 / (2.0 * ax)) ** (k - 1))
        pi.append((1.0 / (2.0 * ax)) * (1.0 - 1.0 / (2.0 * ax)) ** 4)
        chi2 = sum((vk[k] - J * pi[k]) ** 2 / (J * pi[k]) for k in range(6))
        p = igamc(5 / 2.0, chi2 / 2.0)
        if p < alpha:
            fails += 1
        worst = min(worst, p)
    return Result("Random excursions", _family_p(worst, 8),
                  detail=f"J={J} cycles, {fails}/8 states below alpha "
                         f"(chance allows ~{_multi_allowance(8, alpha):.1f}), "
                         f"raw min p={worst:.3e}",
                  alpha=alpha, subtests=8, worst_p=worst)


def random_excursions_variant(bits, alpha=DEFAULT_ALPHA):
    n = len(bits)
    walk, cyc = _cycles(bits)
    J = len(cyc)
    if J < 500:
        return Result("Random excursions variant",
                      skipped=f"needs >= 500 zero-crossing cycles, found {J}")
    worst = 1.0
    fails = 0
    for x in list(range(-9, 0)) + list(range(1, 10)):
        xi = sum(1 for v in walk if v == x)
        den = math.sqrt(2.0 * J * (4.0 * abs(x) - 2.0))
        p = math.erfc(abs(xi - J) / den)
        if p < alpha:
            fails += 1
        worst = min(worst, p)
    return Result("Random excursions variant", _family_p(worst, 18),
                  detail=f"J={J} cycles, {fails}/18 states below alpha "
                         f"(chance allows ~{_multi_allowance(18, alpha):.1f}), "
                         f"raw min p={worst:.3e}",
                  alpha=alpha, subtests=18, worst_p=worst)


# ----------------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------------

ALL_TESTS = [
    (frequency,                  "Frequency (monobit)"),
    (block_frequency,            "Block frequency"),
    (runs,                       "Runs"),
    (longest_run_of_ones,        "Longest run of ones"),
    (binary_matrix_rank,         "Binary matrix rank"),
    (spectral,                   "Spectral (DFT)"),
    (non_overlapping_template,   "Non-overlapping template"),
    (overlapping_template,       "Overlapping template"),
    (universal,                  "Maurer's universal"),
    (linear_complexity,          "Linear complexity"),
    (serial,                     "Serial"),
    (approximate_entropy,        "Approximate entropy"),
    (cumulative_sums,            "Cumulative sums"),
    (random_excursions,          "Random excursions"),
    (random_excursions_variant,  "Random excursions variant"),
]

# Tests omitted by fast=True. Berlekamp-Massey over 200+ blocks and the universal
# test's table walk are the two that actually dominate runtime; both are pure
# Python and neither vectorises usefully.
_SLOW = {linear_complexity, universal}


def run_all(bits, alpha=DEFAULT_ALPHA, fast=False):
    """Run the suite over `bits` (a sequence of 0/1 ints).

    fast=True OMITS the two slowest tests outright and says so in their skip
    reason. It used to instead cap the non-overlapping template count, which was
    a mistake: silently changing a test's parameters while keeping its name means
    the calibrated false-positive rate no longer belongs to the thing being run.
    Omitting a test is honest and visible; redefining one is not.

    Tests whose length is below RECOMMENDED_N are marked advisory rather than
    pass/fail. See the comment on that table.
    """
    bits = list(bits)
    n = len(bits)
    out = []
    for fn, name in ALL_TESTS:
        if fast and fn in _SLOW:
            out.append(Result(name, skipped="omitted in fast mode (slow test)"))
            continue
        r = fn(bits, alpha=alpha)
        rec = RECOMMENDED_N.get(r.name)
        if not r.skipped and rec is not None and n < rec[0]:
            r.advisory = True
            r.advisory_reason = (f"n={n} < recommended {rec[0]} ({rec[1]})")
        out.append(r)
    return out


def tally(results):
    """(passed, failed, advisory, skipped) where `failed` counts only quotable
    failures - a test out of its length regime is never counted as a failure."""
    p = sum(1 for r in results if not r.skipped and not r.advisory and r.passed)
    f = sum(1 for r in results if r.counts_as_failure)
    a = sum(1 for r in results if r.advisory)
    s = sum(1 for r in results if r.skipped)
    return p, f, a, s


def format_report(results, alpha=DEFAULT_ALPHA):
    lines = []
    w = max(len(r.name) for r in results)
    multi = False
    advis = False
    for r in results:
        if r.skipped:
            lines.append(f"  {r.name:<{w}}  {'SKIP':>6}          {r.skipped}")
            continue
        if r.advisory:
            verdict = "ADVIS"
            advis = True
        else:
            verdict = "PASS" if r.passed else "FAIL"
        mark = ""
        if r.subtests and r.subtests > 1:
            mark = f" [{r.subtests} sub-tests]"
            multi = True
        extra = f"  <{r.advisory_reason}>" if r.advisory else ""
        lines.append(f"  {r.name:<{w}}  {verdict:>6}  p={r.p_value:.6f}"
                     f"{mark}  {r.detail}{extra}")
    npass, nfail, nadv, nskip = tally(results)
    lines.append("")
    lines.append(f"  {npass} passed, {nfail} failed at alpha={alpha}"
                 f"  ({nadv} advisory - out of length regime, {nskip} skipped)")
    if advis:
        lines.append("")
        lines.append("  ADVIS rows are NOT failures and NOT passes. The statistic is defined at")
        lines.append("  this length but its reference distribution is asymptotic, and below the")
        lines.append("  recommended n its tail is measurably too heavy - so a small p there is")
        lines.append("  evidence about the approximation, not about the source. Reporting these")
        lines.append("  as failures is how a good source gets falsely accused. To turn them into")
        lines.append("  real verdicts, supply a longer stream; the binding constraint is 1e6 bits.")
    if multi:
        lines.append("")
        lines.append("  Rows marked [k sub-tests] produce k p-values, not one. The p shown and")
        lines.append("  the verdict both use the Bonferroni family value min(1, k*p_min), which")
        lines.append("  is valid under arbitrary dependence between sub-tests; the raw minimum")
        lines.append("  in the detail column is NOT a p-value and must not be compared to alpha.")
        lines.append("  This holds the false-positive rate at or below alpha at some cost in")
        lines.append("  sensitivity. The sub-test failure count is given for information: it")
        lines.append("  separates 'one sub-test was unlucky' from 'many deviated together'.")
    return "\n".join(lines)
