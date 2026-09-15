"""
NIST SP 800-90B min-entropy estimators for binary sources.

Why this file exists separately from nist_sp800_22.py
-----------------------------------------------------
SP 800-22 answers "is this stream distinguishable from random?" and an
AES-conditioned counter passes all of it. SP 800-90B answers the different and
harder question "how much entropy does the SOURCE actually have?", and its
predictor-based estimators are what catch periodic or otherwise structured
sources that the frequency-domain tests are blind to by construction.

The reported min-entropy is the MINIMUM over all estimators, as the standard
requires. A single low estimator is a verdict, not an outlier.

Implementation honesty
----------------------
Exact per the standard: Most Common Value, Collision, Markov, t-Tuple,
Longest Repeated Substring.

Documented deviations, both labelled in their output:
  * `compression`: the standard's 6.3.4 estimator uses a Maurer-style
    distance statistic with a numerically-solved G(p). This implements a
    practical LZMA/zlib compression bound instead. It is a valid upper bound on
    entropy content and is far more legible in a report, but it is not the
    exact 6.3.4 statistic. Do not label it as such.
  * predictor local bounds: the standard solves an exact recurrence for the
    longest-run bound. This uses the Chen-Stein/Poisson approximation
    N*(1-p)*p^r = -ln(0.99), which is standard practice and accurate for the
    run lengths that arise here.
"""

import math
import zlib
import lzma

Z = 2.576  # 99% one-sided normal quantile, per the standard


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

class Estimate:
    __slots__ = ("name", "min_entropy", "detail", "exact")

    def __init__(self, name, min_entropy, detail="", exact=True):
        self.name = name
        self.min_entropy = min_entropy
        self.detail = detail
        self.exact = exact

    def __repr__(self):
        return f"<{self.name}: H_min={self.min_entropy:.6f} b/b>"


def _upper_bound(p, n):
    """One-sided 99% upper confidence bound on a proportion."""
    if n <= 1:
        return 1.0
    return min(1.0, p + Z * math.sqrt(p * (1.0 - p) / (n - 1)))


def _h(p):
    if p <= 0:
        return float("inf")
    if p >= 1:
        return 0.0
    return -math.log2(p)


def _solve_local(r, N):
    """Upper bound on success probability implied by a longest correct-prediction
    run of length r out of N predictions.

    Uses the Chen-Stein/Poisson approximation
        E[# runs of length >= r] = N * (1-p) * p^r = -ln(0.99)
    solved for p.

    CAREFUL: that expression is zero at both p=0 and p=1 and peaks at
    p = r/(r+1), so the equation has TWO roots. Only the LOWER one is
    meaningful; the upper root is an artefact of the approximation breaking
    down when the whole sequence is essentially one run. Bisecting over
    [0, r/(r+1)] selects the correct root. Searching [0.5, 1] instead returns
    the spurious root and reports H_min ~ 0 for perfectly good random data,
    which is how this bug was found.

    Everything is done in log space because p^r underflows for large r.
    """
    if r <= 0 or N <= 0:
        return 0.5
    log_target = math.log(-math.log(0.99))
    peak = r / (r + 1.0)

    def g(p):
        # log(N) + log(1-p) + r*log(p) - log(target); increasing on [0, peak]
        return math.log(N) + math.log1p(-p) + r * math.log(p) - log_target

    # if even the peak cannot reach the target, the run is uninformative
    if g(peak) < 0:
        return 0.5
    lo, hi = 1e-12, peak
    if g(lo) > 0:
        return 0.5
    for _ in range(300):
        mid = (lo + hi) / 2.0
        if g(mid) < 0:
            lo = mid
        else:
            hi = mid
    return max(0.5, hi)


# ----------------------------------------------------------------------------
# 6.3.1 Most Common Value
# ----------------------------------------------------------------------------

def most_common_value(bits):
    n = len(bits)
    ones = sum(bits)
    p = max(ones, n - ones) / n
    pu = _upper_bound(p, n)
    return Estimate("Most Common Value", _h(pu),
                    f"p_max={p:.6f} upper={pu:.6f}")


# ----------------------------------------------------------------------------
# 6.3.2 Collision
# ----------------------------------------------------------------------------

def collision(bits):
    """Binary collision estimator. For two symbols a repeat must occur by the
    third sample, so E[T] = 2 + 2p(1-p)."""
    n = len(bits)
    times = []
    i = 0
    while i + 1 < n:
        if bits[i] == bits[i + 1]:
            times.append(2)
            i += 2
        elif i + 2 < n:
            times.append(3)
            i += 3
        else:
            break
    v = len(times)
    if v < 2:
        return Estimate("Collision", float("nan"), "too few collisions")
    mean = sum(times) / v
    var = sum((t - mean) ** 2 for t in times) / (v - 1)
    sigma = math.sqrt(var)
    mean_lo = mean - Z * sigma / math.sqrt(v)
    c = (mean_lo - 2.0) / 2.0          # = p(1-p)
    if c >= 0.25:
        p = 0.5
    elif c <= 0:
        p = 1.0
    else:
        p = (1.0 + math.sqrt(1.0 - 4.0 * c)) / 2.0
    return Estimate("Collision", _h(p),
                    f"v={v} mean_T={mean:.4f} lower={mean_lo:.4f} p={p:.6f}")


def ideal_collision_hmin(n, sigmas=0.0):
    """The value `collision()` returns for a PERFECT binary source at length n.

    This is not a test - it is the finite-sample floor of the collision
    estimator, and it matters because collision is usually the binding (lowest)
    estimator on good binary data. The reason is structural: E[T] = 2 + 2p(1-p)
    has zero derivative in p at p = 0.5, so inverting it near the unbiased point
    amplifies the confidence-interval slack enormously. A small uncertainty in
    E[T] becomes a large excursion in p, and hence a large deficit in H_min.

    Consequence for reporting: an ideal source scores about 0.78 at n = 20000
    and about 0.91 at n = 1e6. So "H_min = 0.78" on 20k bits is the ceiling, not
    a deficiency of the source, and a min-entropy figure must always be quoted
    with the sample size beside it. Use at least 1e6 bits for any number that
    goes in front of an examiner.

    `sigmas` widens the result downward to account for sampling variation in the
    observed mean itself. With sigmas=0 this returns the EXPECTED score, which a
    real ideal sample lands above or below with probability about a half - so it
    is useless as a pass/fail bar. sigmas=3 gives a bar an ideal source clears
    essentially always, which is what a validation check needs.
    """
    v = int(n / 2.5)                       # E[T] = 2.5, so 2.5 bits per segment
    if v < 2:
        return float("nan")
    sigma = 0.5                            # var(T) = 0.25 at p = 0.5
    # collision() subtracts Z*sigma/sqrt(v) from the observed mean; the observed
    # mean itself has standard error sigma/sqrt(v). Both terms scale together.
    mean_lo = 2.5 - (Z + sigmas) * sigma / math.sqrt(v)
    c = (mean_lo - 2.0) / 2.0
    if c >= 0.25:
        return 1.0
    if c <= 0.0:
        return 0.0
    p = (1.0 + math.sqrt(1.0 - 4.0 * c)) / 2.0
    return _h(p)


def get(results, name_prefix):
    """Fetch one estimate by name prefix, for targeted checks."""
    for r in results:
        if r.name.startswith(name_prefix):
            return r
    return None


def ideal_mcv_hmin(n, sigmas=0.0):
    """The value `most_common_value()` returns for a PERFECT binary source at n.

    Two separate effects keep this below 1.0 even on flawless data, and both are
    finite-sample artefacts rather than defects:

      1. p_max = max(ones, zeros)/n is an absolute value, so it is >= 0.5 always
         and its expectation sits strictly above 0.5. With ones ~ Bin(n, 1/2),
         E|ones - n/2| = sqrt(n)/2 * sqrt(2/pi), giving
             E[p_max] = 0.5 + 1/sqrt(2*pi*n).
      2. The estimator then applies a 99% UPPER confidence bound to p_max, which
         pushes it up by a further Z*sqrt(p(1-p)/(n-1)).

    At n = 20000 that lands at H_min ~ 0.966, not 1.0. Checking "MCV on random
    data is within 0.05 of 1.0" therefore sits about 2.7 sigma from the mean and
    false-alarms every few runs - which is how this function came to exist.

    `sigmas` widens the bound downward using sd(|ones - n/2|)/n, the half-normal
    standard deviation sqrt(1 - 2/pi) * sqrt(n)/2 / n.
    """
    p = 0.5 + 1.0 / math.sqrt(2.0 * math.pi * n)
    if sigmas:
        p += sigmas * math.sqrt(1.0 - 2.0 / math.pi) / (2.0 * math.sqrt(n))
    p = min(p, 1.0)
    return _h(_upper_bound(p, n))


# ----------------------------------------------------------------------------
# 6.3.3 Markov
# ----------------------------------------------------------------------------

def markov(bits, chain=128):
    """Highest-probability chain of length `chain` through the estimated
    first-order Markov model, per the standard's binary Markov estimator."""
    n = len(bits)
    c0 = sum(1 for b in bits[:-1] if b == 0)
    c1 = (n - 1) - c0
    if c0 == 0 or c1 == 0:
        return Estimate("Markov", 0.0, "degenerate: source is constant")
    t = {(0, 0): 0, (0, 1): 0, (1, 0): 0, (1, 1): 0}
    for i in range(n - 1):
        t[(bits[i], bits[i + 1])] += 1
    p00 = min(1.0, t[(0, 0)] / c0 + Z * math.sqrt(t[(0, 0)] / c0 * (1 - t[(0, 0)] / c0) / c0))
    p11 = min(1.0, t[(1, 1)] / c1 + Z * math.sqrt(t[(1, 1)] / c1 * (1 - t[(1, 1)] / c1) / c1))
    p01 = 1.0 - p00
    p10 = 1.0 - p11
    P = {(0, 0): p00, (0, 1): p01, (1, 0): p10, (1, 1): p11}
    ones = sum(bits)
    p_init = [_upper_bound((n - ones) / n, n), _upper_bound(ones / n, n)]

    # DP for the max-probability path of `chain` states
    best = [math.log2(p_init[0]) if p_init[0] > 0 else -math.inf,
            math.log2(p_init[1]) if p_init[1] > 0 else -math.inf]
    for _ in range(chain - 1):
        nxt = [-math.inf, -math.inf]
        for s in (0, 1):
            if best[s] == -math.inf:
                continue
            for d in (0, 1):
                pr = P[(s, d)]
                if pr <= 0:
                    continue
                cand = best[s] + math.log2(pr)
                if cand > nxt[d]:
                    nxt[d] = cand
        best = nxt
    log_pmax = max(best)
    hmin = min(1.0, -log_pmax / chain)
    return Estimate("Markov", hmin,
                    f"chain={chain} P00={p00:.4f} P11={p11:.4f}")


# ----------------------------------------------------------------------------
# 6.3.4 Compression  (practical bound, see module docstring)
# ----------------------------------------------------------------------------

def compression(bits):
    n = len(bits)
    packed = bytes(int(''.join(str(b) for b in bits[i:i + 8]).ljust(8, '0'), 2)
                   for i in range(0, n, 8))
    z = len(zlib.compress(packed, 9))
    x = len(lzma.compress(packed, preset=9))
    best = min(z, x)
    hmin = min(1.0, best * 8.0 / n)
    return Estimate("Compression (practical bound)", hmin,
                    f"{len(packed)} B -> zlib {z} B, lzma {x} B "
                    f"({best/len(packed)*100:.2f}%)",
                    exact=False)


# ----------------------------------------------------------------------------
# 6.3.5 t-Tuple
# ----------------------------------------------------------------------------

def t_tuple(bits, thresh=35):
    n = len(bits)
    best_p = 0.0
    t_used = 0
    t = 1
    while True:
        counts = {}
        m = n - t + 1
        if m <= 0:
            break
        for i in range(m):
            key = tuple(bits[i:i + t])
            counts[key] = counts.get(key, 0) + 1
        mx = max(counts.values())
        if mx < thresh:
            break
        p = (mx / m) ** (1.0 / t)
        if p > best_p:
            best_p = p
            t_used = t
        t += 1
        if t > 64:
            break
    if best_p == 0.0:
        return Estimate("t-Tuple", float("nan"), "no tuple reached threshold")
    pu = _upper_bound(best_p, n)
    return Estimate("t-Tuple", _h(pu), f"t_max={t_used} p={best_p:.6f} upper={pu:.6f}")


# ----------------------------------------------------------------------------
# 6.3.6 Longest Repeated Substring
# ----------------------------------------------------------------------------

def lrs(bits, thresh=35):
    n = len(bits)
    s = ''.join(str(b) for b in bits)
    # u: smallest length whose most common tuple falls below the threshold
    u = 1
    while u <= 64:
        counts = {}
        m = n - u + 1
        for i in range(m):
            counts[s[i:i + u]] = counts.get(s[i:i + u], 0) + 1
        if max(counts.values()) < thresh:
            break
        u += 1
    # v: longest repeated substring length, via binary search on "any repeat".
    # Uses a Rabin-Karp rolling hash: materialising length-L slices for large L
    # would allocate O(n*L) bytes and is the obvious way to run out of memory
    # on a periodic stream, where L grows to the cap.
    vals = [1 if c == '1' else 0 for c in s]
    MOD = (1 << 61) - 1
    BASE = 1000003

    def has_repeat(L):
        if L <= 0 or L > n:
            return False
        h = 0
        for i in range(L):
            h = (h * BASE + vals[i] + 1) % MOD
        top = pow(BASE, L - 1, MOD)
        seen = {h: [0]}
        for i in range(1, n - L + 1):
            h = ((h - (vals[i - 1] + 1) * top) * BASE + vals[i + L - 1] + 1) % MOD
            bucket = seen.get(h)
            if bucket is not None:
                cand = s[i:i + L]
                for j in bucket:
                    if s[j:j + L] == cand:      # guard against hash collision
                        return True
                bucket.append(i)
            else:
                seen[h] = [i]
        return False

    lo, hi = 1, min(n - 1, 4096)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if has_repeat(mid):
            lo = mid
        else:
            hi = mid - 1
    v = lo
    best = 0.0
    for W in range(u, min(v, u + 64) + 1):
        counts = {}
        m = n - W + 1
        if m < 2:
            break
        for i in range(m):
            counts[s[i:i + W]] = counts.get(s[i:i + W], 0) + 1
        num = sum(c * (c - 1) / 2 for c in counts.values())
        den = m * (m - 1) / 2
        if den <= 0 or num <= 0:
            continue
        pw = (num / den) ** (1.0 / W)
        best = max(best, pw)
    if best <= 0:
        return Estimate("Longest Repeated Substring", float("nan"), "no repeats")
    pu = _upper_bound(best, n)
    return Estimate("Longest Repeated Substring", _h(pu),
                    f"u={u} v={v} p={best:.6f} upper={pu:.6f}")


# ----------------------------------------------------------------------------
# predictor framework  (6.3.7 - 6.3.10)
# ----------------------------------------------------------------------------

def _predictor_result(name, correct, N, longest_run, detail=""):
    if N <= 0:
        return Estimate(name, float("nan"), "no predictions made")
    pg = correct / N
    pg_u = _upper_bound(pg, N)
    pl = _solve_local(longest_run, N)
    p = max(pg_u, pl)
    return Estimate(name, _h(p),
                    f"acc={pg*100:.4f}% global_ub={pg_u:.6f} "
                    f"run={longest_run} local={pl:.6f} {detail}",
                    exact=False)


def multi_mcw(bits, windows=(63, 255, 1023, 4095)):
    """6.3.7 Multi Most Common in Window.

    Window counts are maintained incrementally. The naive version recomputes
    sum(bits[i-w:i]) for every window at every step, which is O(n * sum(w)) --
    about 1e8 Python operations at n=20000 with a 4095-wide window, and 5e8 at
    n=100000. Incremental counts make it O(n * len(windows)).
    """
    n = len(bits)
    K = len(windows)
    score = [0] * K
    correct = 0
    N = 0
    run = 0
    best_run = 0
    start = min(windows) + 1
    if n <= start:
        return Estimate("MultiMCW predictor", float("nan"), "too short")

    # ones[j] / size[j] describe the segment bits[max(0, i-w_j) : i]
    ones = []
    size = []
    for w in windows:
        lo = max(0, start - w)
        seg = bits[lo:start]
        ones.append(sum(seg))
        size.append(len(seg))

    for i in range(start, n):
        preds = [1 if ones[j] * 2 > size[j] else 0 for j in range(K)]
        winner = score.index(max(score))
        pred = preds[winner]
        actual = bits[i]
        N += 1
        if pred == actual:
            correct += 1
            run += 1
            if run > best_run:
                best_run = run
        else:
            run = 0
        for j in range(K):
            if preds[j] == actual:
                score[j] += 1
        # slide every window forward by one: bits[i] enters, bits[i-w] leaves
        for j in range(K):
            ones[j] += actual
            size[j] += 1
            drop = i - windows[j]
            if drop >= 0:
                ones[j] -= bits[drop]
                size[j] -= 1
    return _predictor_result("MultiMCW predictor", correct, N, best_run,
                             f"windows={windows}")


def lag(bits, D=128):
    """6.3.8 Lag predictor. This is the estimator that catches periodicity.

    D = 128 IS THE VALUE SP 800-90B SPECIFIES, and it is kept here for exactly
    that reason - but it is a hard resolution limit that has to be understood
    before this number is quoted. The predictor only ever proposes bits[i-d] for
    d in 1..D, so a stream whose period exceeds D is not merely estimated poorly,
    it is structurally invisible: the winning predictor cannot be expressed.

    That is not hypothetical. On the RRAM golden model, whose output is exactly
    periodic with period 170 and therefore has an entropy rate of exactly ZERO,
    sweeping D over 100,000 samples gives:

        D     H_min      accuracy    best_lag
        128   0.472570   71.7008%    85        <- the value the standard mandates
        170   0.000095   99.9699%    170
        256   0.000095   99.9759%    170
        512   0.000018   99.9910%    170

    At the mandated D this estimator reports 0.47 bits per bit for a stream with
    no entropy at all, and picks lag 85 - a harmonic of the real period, which is
    the closest thing to 170 it is able to say. One bit past the period and it
    collapses to 1e-4. So the standard's own parameter choice hides a defect of
    precisely the kind the standard exists to catch, whenever the period lands
    between 129 and the sample length.

    Two consequences for how this suite is used. First, D=128 must stay the
    default, because a "SP 800-90B min-entropy" figure computed with non-standard
    parameters is not comparable to anyone else's and should not be presented as
    one. Second, the compliant number is therefore an UPPER bound that can be
    loose by orders of magnitude, so lag_extended() below is run alongside it as
    a labelled diagnostic. What saved the assessment here was not this estimator
    but the compression estimator (0.0202) and the structural period scan; had
    the design been judged on the mandated lag figure alone it would have looked
    like a usable entropy source.
    """
    n = len(bits)
    if n <= D + 1:
        D = max(1, n // 2)
    score = [0] * D
    correct = 0
    N = 0
    run = 0
    best_run = 0
    for i in range(D, n):
        winner = score.index(max(score))
        pred = bits[i - (winner + 1)]
        actual = bits[i]
        N += 1
        if pred == actual:
            correct += 1
            run += 1
            best_run = max(best_run, run)
        else:
            run = 0
        for j in range(D):
            if bits[i - (j + 1)] == actual:
                score[j] += 1
    best_lag = score.index(max(score)) + 1
    return _predictor_result("Lag predictor", correct, N, best_run,
                             f"D={D} best_lag={best_lag}")


def lag_extended(bits, ds=None, hint=None):
    """Lag predictor at LARGER D. NOT SP 800-90B COMPLIANT - a diagnostic only.

    Deliberately kept out of ALL_ESTIMATORS so that run_all() and min_entropy()
    stay standards-conformant. Mixing this into the assessed figure would produce
    a number that is tighter than the standard's and cannot be labelled with the
    standard's name, which is the worse of the two errors available here: an
    incomparable result presented as a comparable one.

    Reported alongside lag() because the compliant D=128 result is an upper bound
    that a period in (128, n] makes arbitrarily loose - see lag() for the measured
    sweep where a zero-entropy stream scores 0.47 bits/bit at D=128.

    `hint` is a period from the structural scan, if one was found. It is included
    in the sweep so the predictor is given at least one D that can express the
    period actually present; without it the sweep can still straddle the period
    and understate how predictable the stream is.

    Cost is O(n * D), so the ladder is capped relative to n rather than fixed.
    """
    n = len(bits)
    if ds is None:
        ds = [128, 256, 512, 1024]
        ds = [d for d in ds if d * 8 <= n] or [max(1, n // 8)]
    if hint:
        ds = sorted(set(list(ds) + [hint, hint + 1]))
    ds = [d for d in ds if 0 < d < n - 1]
    if not ds:
        return Estimate("Lag predictor (extended D)", float("nan"),
                        "stream too short for any D", exact=False)
    best = None
    for d in ds:
        r = lag(bits, D=d)
        if r.min_entropy != r.min_entropy:
            continue
        # The tightest bound over the ladder. This is a legitimate minimum, not
        # p-hacking: each D is a different predictor, and SP 800-90B's own rule
        # for its predictors is to take the most predictive result, because a
        # bound only has to be achievable by SOME attacker to be real.
        if best is None or r.min_entropy < best[1].min_entropy:
            best = (d, r)
    d, r = best
    return Estimate("Lag predictor (extended D)", r.min_entropy,
                    f"{r.detail} | swept D over {ds}, tightest at D={d} "
                    f"(NON-STANDARD, diagnostic only)", exact=False)


def multi_mmc(bits, D=16):
    """6.3.9 Multi Markov Model with Counting."""
    n = len(bits)
    if n <= D + 2:
        return Estimate("MultiMMC predictor", float("nan"), "too short")
    models = [dict() for _ in range(D)]
    score = [0] * D
    correct = 0
    N = 0
    run = 0
    best_run = 0
    for i in range(D, n):
        preds = []
        for d in range(1, D + 1):
            ctx = tuple(bits[i - d:i])
            tbl = models[d - 1].get(ctx)
            if tbl is None:
                preds.append(None)
            else:
                preds.append(0 if tbl[0] >= tbl[1] else 1)
        winner = score.index(max(score))
        pred = preds[winner]
        actual = bits[i]
        if pred is not None:
            N += 1
            if pred == actual:
                correct += 1
                run += 1
                best_run = max(best_run, run)
            else:
                run = 0
        for j in range(D):
            if preds[j] is not None and preds[j] == actual:
                score[j] += 1
        for d in range(1, D + 1):
            ctx = tuple(bits[i - d:i])
            tbl = models[d - 1].setdefault(ctx, [0, 0])
            tbl[actual] += 1
    best_order = score.index(max(score)) + 1
    return _predictor_result("MultiMMC predictor", correct, N, best_run,
                             f"D={D} best_order={best_order}")


def lz78y(bits, maxlen=32, max_dict=65536):
    """6.3.10 LZ78Y predictor."""
    n = len(bits)
    if n <= maxlen + 2:
        return Estimate("LZ78Y predictor", float("nan"), "too short")
    d = {}
    correct = 0
    N = 0
    run = 0
    best_run = 0
    for i in range(maxlen, n):
        pred = None
        for L in range(maxlen, 0, -1):
            ctx = tuple(bits[i - L:i])
            tbl = d.get(ctx)
            if tbl is not None:
                pred = 0 if tbl[0] >= tbl[1] else 1
                break
        actual = bits[i]
        if pred is not None:
            N += 1
            if pred == actual:
                correct += 1
                run += 1
                best_run = max(best_run, run)
            else:
                run = 0
        if len(d) < max_dict:
            for L in range(1, maxlen + 1):
                ctx = tuple(bits[i - L:i])
                tbl = d.setdefault(ctx, [0, 0])
                tbl[actual] += 1
    return _predictor_result("LZ78Y predictor", correct, N, best_run,
                             f"dict={len(d)}")


# ----------------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------------

ALL_ESTIMATORS = [
    most_common_value,
    collision,
    markov,
    compression,
    t_tuple,
    lrs,
    multi_mcw,
    lag,
    multi_mmc,
    lz78y,
]

# FAST_ESTIMATORS must retain the ability to detect periodicity.
#
# It originally did not, and that was a serious defect rather than a tuning
# choice. The set was [most_common_value, collision, markov, compression, lag],
# and measured against the lfsr8 control at n=20,000 - period 255, entropy rate
# exactly zero - only two of the ten estimators catch it at all:
#
#     Most Common Value              0.967595   misses
#     Collision                      1.000000   misses
#     Markov                         0.962863   misses
#     Compression                    0.120000   misses
#     t-Tuple                        0.116804   misses
#     Longest Repeated Substring     0.056614   misses
#     MultiMCW predictor             0.970650   misses
#     Lag predictor                  1.000000   misses  <- reports FULL entropy
#     MultiMMC predictor             0.000480   CATCHES
#     LZ78Y predictor                0.000474   CATCHES
#
# Both catchers were in the omitted set, so fast mode was structurally blind to
# exactly the failure mode this project exists to find. Note also the lag row:
# at the mandated D=128 it does not merely miss a period-255 stream, it returns
# the MAXIMUM 1.000000, because its accuracy lands at 17.65% - reliably worse
# than chance, which is just as exploitable as reliably better, but the
# standard's one-sided bound p_global = p + Z*sqrt(...) discards it.
#
# The exclusion was not even buying speed. Timed on 100,000 bits of the RRAM
# model: multi_mmc 1.92s and lz78y 2.13s, against lag 1.57s which was already
# included. The genuinely expensive ones are t_tuple 5.69s and lrs 5.20s, and
# those two miss the defect anyway. So both catchers are now in the fast set;
# it is about 4s slower at n=1e5 and no longer lies about periodic sources.
FAST_ESTIMATORS = [most_common_value, collision, markov, compression, lag,
                   multi_mmc, lz78y]


def run_all(bits, fast=False):
    bits = list(bits)
    ests = FAST_ESTIMATORS if fast else ALL_ESTIMATORS
    out = []
    for e in ests:
        try:
            out.append(e(bits))
        except Exception as exc:                    # keep the suite running
            out.append(Estimate(e.__name__, float("nan"), f"error: {exc}"))
    return out


def min_entropy(results):
    vals = [r.min_entropy for r in results
            if r.min_entropy == r.min_entropy]      # drop NaN
    return min(vals) if vals else float("nan")


def format_report(results):
    lines = []
    w = max(len(r.name) for r in results)
    for r in results:
        if r.min_entropy != r.min_entropy:
            lines.append(f"  {r.name:<{w}}       n/a   {r.detail}")
        else:
            flag = "" if r.exact else "  [approx]"
            lines.append(f"  {r.name:<{w}}  {r.min_entropy:8.6f}   {r.detail}{flag}")
    h = min_entropy(results)
    lines.append("")
    lines.append(f"  ASSESSED MIN-ENTROPY = {h:.6f} bits per bit  (minimum over all estimators)")
    return "\n".join(lines)
