"""Real-basis fundamental fit and conditional raw-input operator norm."""
import math

import numpy as np

RANK_TOLERANCE = 64*np.finfo(float).eps


def _subnyquist(fs, freq):
    # Reject aliased/singular domains before trig argument error creates rank.
    return math.isfinite(fs) and math.isfinite(freq) and 0 < freq < fs/2


def filter_samples(x, decay):
    """Existing mimic FIR, including its initialized first sample."""
    x = np.asarray(x, dtype=float)
    if decay is None or not len(x):
        return x.copy()
    y = np.empty_like(x)
    y[0] = (1-decay)*x[0]
    y[1:] = x[1:]-decay*x[:-1]
    return y


def _sum_windows(x, n):
    cumulative = np.concatenate(([0.], np.cumsum(x)))
    return cumulative[n:]-cumulative[:-n]


def _gram(u, v, total):
    cc, ss, cs = total(u*u), total(v*v), total(u*v)
    det = cc*ss-cs*cs
    good = np.isfinite(det) & (cc > 0) & (ss > 0) & (det > RANK_TOLERANCE*(cc+ss)**2)
    return cc, ss, cs, det, good


def sliding_fundamental(x, t, fs, freq, n, decay):
    """Fit filtered cosine/sine coefficients on each complete support."""
    x, t = np.asarray(x, dtype=float), np.asarray(t, dtype=float)
    if x.ndim != 1 or t.shape != x.shape:
        raise ValueError('Matching one-dimensional samples and times required.')
    out = np.full(x.size, np.nan+0j, dtype=complex)
    if not _subnyquist(fs, freq) or n < 2 or x.size < n:
        return out
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        phase = 2*np.pi*freq*t
        u = filter_samples(np.cos(phase), decay)
        v = filter_samples(np.sin(phase), decay)
        y = filter_samples(x, decay)
        def total(z):
            return _sum_windows(z, n)
        cc, ss, cs, det, good = _gram(u, v, total)
        yc, ys = total(y*u), total(y*v)
        fitted = ((yc*ss-ys*cs)-1j*(ys*cc-yc*cs))/(np.sqrt(2)*det)
        good &= np.isfinite(fitted)
        out[n-1:] = np.where(good, fitted, np.nan+0j)
    return out


def kernel_l1(fs, freq, n, decay):
    """Largest initial/steady raw-sample L1 coefficient norm on uniform grids.

    Basis rotation at a different absolute origin leaves complex coefficient
    magnitudes unchanged. The prior FIR input sample is included explicitly.
    """
    if not _subnyquist(fs, freq) or not 2 <= n <= 100000:
        raise ValueError('Research kernel requires a sub-Nyquist frequency and2..100000 samples.')
    phase = (2*np.pi*(freq/fs))*np.arange(-1, n)
    raw_u, raw_v = np.cos(phase), np.sin(phase)
    factors = []
    for initial in (False, True):
        if decay is None:
            u, v = raw_u[1:], raw_v[1:]
        else:
            u = raw_u[1:]-decay*raw_u[:-1]
            v = raw_v[1:]-decay*raw_v[:-1]
            if initial:
                u[0], v[0] = (1-decay)*raw_u[1], (1-decay)*raw_v[1]
        cc, ss, cs, det, good = _gram(u, v, np.sum)
        if not good:
            raise ValueError('Rank-deficient conditional fundamental kernel.')
        weights = ((ss*u-cs*v)-1j*(cc*v-cs*u))/(np.sqrt(2)*det)
        if decay is not None:
            raw = np.zeros(n+1, complex)
            raw[1:] += weights
            raw[:-1] -= decay*weights
            if initial:
                raw[0] = 0
                raw[1] -= decay*weights[0]
            weights = raw
        factors.append(math.fsum(abs(z) for z in weights))
    return max(factors)


def legacy_fundamental(x, t, fs, freq, n, decay):
    """Historical production operator; experimental fit requires explicit opt-in."""
    x = filter_samples(x, decay)
    gain = 1 if decay is None else 1-decay*np.exp(-2j*np.pi*freq/fs)
    cumulative = np.concatenate(([0j], np.cumsum(x*np.exp(-2j*np.pi*freq*t))))
    out = np.full(x.size, np.nan+0j, dtype=complex)
    if x.size >= n:
        out[n-1:] = ((2./n)*(cumulative[n:]-cumulative[:-n]))/math.sqrt(2.)/gain
    return out


def legacy_kernel_l1(fs, freq, n, decay):
    """Historical scalar-kernel bound retained for default production phasors."""
    factor = math.sqrt(2)
    if decay is not None:
        gain = abs(1-decay*np.exp(-2j*math.pi*(freq/fs)))
        if gain == 0:
            raise ValueError('Unrepresentable mimic response.')
        factor *= (n-1)/n+(1+decay)/(n*gain)
    return factor
