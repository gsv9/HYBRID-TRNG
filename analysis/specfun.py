"""
Special functions needed by the NIST test suite, implemented without scipy.

Only three things are required beyond the standard library:
  - erfc / normal CDF   (math.erfc covers this)
  - igamc(a, x): the regularised upper incomplete gamma Q(a,x), used for every
    chi-square p-value in SP 800-22
  - Berlekamp-Massey, used by the linear complexity test

igamc follows the standard series / continued-fraction split (Numerical Recipes
"gammq"): the power series converges quickly for x < a+1, the Lentz continued
fraction for x >= a+1.
"""

import math

_ITMAX = 1000
_EPS = 3.0e-16
_FPMIN = 1.0e-300


def _gser(a, x):
    """Lower regularised incomplete gamma P(a,x) via power series."""
    if x <= 0.0:
        return 0.0
    gln = math.lgamma(a)
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(_ITMAX):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * _EPS:
            break
    return total * math.exp(-x + a * math.log(x) - gln)


def _gcf(a, x):
    """Upper regularised incomplete gamma Q(a,x) via modified Lentz continued fraction."""
    gln = math.lgamma(a)
    b = x + 1.0 - a
    c = 1.0 / _FPMIN
    d = 1.0 / b
    h = d
    for i in range(1, _ITMAX + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = b + an / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def igamc(a, x):
    """Regularised upper incomplete gamma Q(a, x) = 1 - P(a, x).

    This is the function NIST calls igamc(); a chi-square statistic with
    df degrees of freedom has p-value igamc(df/2, chi2/2).
    """
    if x < 0.0 or a <= 0.0:
        raise ValueError(f"igamc domain error: a={a}, x={x}")
    if x == 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gser(a, x)
    return _gcf(a, x)


def igam(a, x):
    """Regularised lower incomplete gamma P(a, x)."""
    return 1.0 - igamc(a, x)


def normal_cdf(z):
    """Standard normal CDF, written via erfc for tail accuracy."""
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def berlekamp_massey(bits):
    """Linear complexity of a binary sequence over GF(2).

    Returns L, the length of the shortest LFSR that generates `bits`.
    `bits` is a sequence of 0/1 ints.
    """
    n = len(bits)
    b = [0] * n
    c = [0] * n
    b[0] = 1
    c[0] = 1
    L = 0
    m = -1
    for N in range(n):
        # discrepancy
        d = bits[N]
        for i in range(1, L + 1):
            d ^= c[i] & bits[N - i]
        if d == 1:
            t = c[:]
            shift = N - m
            for i in range(shift, n):
                c[i] ^= b[i - shift]
            if L <= N // 2:
                L = N + 1 - L
                m = N
                b = t
    return L


def gf2_rank(rows, ncols):
    """Rank over GF(2) of a matrix given as a list of int bitmasks."""
    rows = list(rows)
    rank = 0
    pivot_row = 0
    for col in range(ncols):
        bit = 1 << col
        sel = None
        for r in range(pivot_row, len(rows)):
            if rows[r] & bit:
                sel = r
                break
        if sel is None:
            continue
        rows[pivot_row], rows[sel] = rows[sel], rows[pivot_row]
        for r in range(len(rows)):
            if r != pivot_row and (rows[r] & bit):
                rows[r] ^= rows[pivot_row]
        pivot_row += 1
        rank += 1
        if pivot_row == len(rows):
            break
    return rank


def binom_log_pmf(i, n, p):
    """log P(X = i) for X ~ Bin(n, p), via lgamma."""
    if p <= 0.0:
        return 0.0 if i == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if i == n else -math.inf
    return (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p) + (n - i) * math.log1p(-p))


def binom_sf(k, n, p):
    """Exact binomial survival function P(X >= k) for X ~ Bin(n, p).

    Needed because the usual normal approximation is badly wrong in the regime
    that matters here: validating a test suite's false-positive rate means
    n*p is around 1, where the binomial is strongly right-skewed and a
    mean + 3*sigma bound both over- and under-shoots depending on the tail.

    Computed in log space. The direct form math.comb(n, i) * p**i * (1-p)**(n-i)
    raises OverflowError once n reaches a few hundred, because comb overflows a
    float while p**i underflows to zero - the product is representable but the
    factors are not.
    """
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    total = 0.0
    peak = n * p
    for i in range(k, n + 1):
        term = math.exp(binom_log_pmf(i, n, p))
        total += term
        # terms decay monotonically past the mode; stop once negligible
        if i > peak and term < total * 1e-17 and term > 0.0:
            break
        if term == 0.0 and i > peak:
            break
    return min(1.0, total)


def binom_allowance(n, p, level=1e-3):
    """Largest failure count A such that P(X > A) < level, X ~ Bin(n, p).

    Used as the pass/fail bar when checking that a test suite rejects genuinely
    random data at approximately its nominal rate. `level` is the probability
    that the CHECK itself false-alarms on a perfect source, so it should be much
    smaller than the suite's own alpha.
    """
    for a in range(0, n + 1):
        if binom_sf(a + 1, n, p) < level:
            return a
    return n


def ks_statistic(sample):
    """Two-sided Kolmogorov-Smirnov statistic of `sample` against U[0, 1]."""
    a = sorted(sample)
    m = len(a)
    return max(max((i + 1) / m - a[i], a[i] - i / m) for i in range(m))


def ks_pvalue(d, m):
    """Asymptotic p-value for the KS statistic d on m samples against U[0,1].

    Q(t) = 2 * sum_{j>=1} (-1)^(j-1) exp(-2 j^2 t^2) with t = sqrt(m) * d.

    A p-value rather than a bare statistic is needed whenever several KS tests
    are run together, because only p-values can be multiplicity-corrected. That
    turned out to matter: comparing nine raw KS statistics against a single 1%
    critical value false-alarms on about 9% of runs, which is the same
    multiple-comparison trap the suite itself was fixed for.
    """
    t = math.sqrt(m) * d
    if t <= 0.0:
        return 1.0
    if t < 0.3:                      # series is numerically flat here
        return 1.0
    total = 0.0
    for j in range(1, 101):
        term = math.exp(-2.0 * j * j * t * t)
        total += (-1) ** (j - 1) * term
        if term < 1e-18:
            break
    return max(0.0, min(1.0, 2.0 * total))


def aperiodic_templates(m):
    """All aperiodic m-bit templates, as NIST defines them for the
    non-overlapping template matching test.

    A template B is aperiodic if no proper prefix of B is also a suffix of B,
    i.e. B has no period shorter than m.
    """
    out = []
    for v in range(1 << m):
        bits = tuple((v >> (m - 1 - i)) & 1 for i in range(m))
        periodic = False
        for p in range(1, m):
            if bits[:m - p] == bits[p:]:
                periodic = True
                break
        if not periodic:
            out.append(bits)
    return out
