"""Signal processing chain, steps 1-6 of the brief's section 6.

Phasor convention used everywhere in this package
-------------------------------------------------
A phasor at sample n is the RMS phasor of the fundamental, referenced to the
record's own absolute time origin t = 0, estimated from the full cycle of
samples ENDING at n:

    X(t_n) = (2/N) * sum_{k=n-N+1..n} x[k] * exp(-j*w*t[k])   / sqrt(2)

Referencing to absolute time rather than to the window start means a steady
sinusoid gives a constant phasor, so superimposed quantities are a plain
subtraction and the recovered sync angle in E5 is a physically meaningful
number rather than a window artefact.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

A = np.exp(2j * np.pi / 3.0)


# --------------------------------------------------------------------------
# step 2: frequency tracking
# --------------------------------------------------------------------------
def track_frequency(
    v: np.ndarray, fs: float, nominal: float = 50.0, upto: Optional[int] = None
) -> float:
    """Estimate the fundamental from zero crossings of a pre-fault voltage.

    A fixed 50 Hz assumption biases every DFT that follows, and off-nominal
    excursions are correlated with exactly the large disturbances this system
    exists to analyse, so this is not optional.
    """
    x = v[:upto] if upto else v
    x = np.asarray(x, dtype=float)
    if x.size < int(fs / nominal) * 2:
        return nominal
    x = x - float(np.mean(x))
    sign = np.signbit(x)
    idx = np.nonzero(np.diff(sign.astype(int)) < 0)[0]  # positive-going
    if idx.size < 3:
        return nominal
    # sub-sample crossing by linear interpolation
    cross = []
    for i in idx:
        x0, x1 = x[i], x[i + 1]
        if x1 == x0:
            cross.append(float(i))
        else:
            cross.append(i + x0 / (x0 - x1))
    cross = np.asarray(cross)
    periods = np.diff(cross) / fs
    periods = periods[np.isfinite(periods) & (periods > 0)]
    if periods.size == 0:
        return nominal
    f = 1.0 / float(np.median(periods))
    return f if 0.8 * nominal < f < 1.2 * nominal else nominal


# --------------------------------------------------------------------------
# step 3: decaying DC removal (mimic filter)
# --------------------------------------------------------------------------
def mimic_filter(x: np.ndarray, fs: float, freq: float, tau: float) -> Tuple[np.ndarray, complex]:
    """Cancel the decaying DC pole with a matched FIR zero.

    The filter is (1 - a*z^-1) with a = exp(-dt/tau), which places a zero
    exactly on the DC pole. It also scales and rotates the fundamental, so
    the exact complex response at the fundamental is returned and divided out
    of the phasor afterwards. A plain full-cycle DFT does NOT remove decaying
    DC, which is the largest phasor error source in the first cycles.
    """
    dt = 1.0 / fs
    a = math.exp(-dt / max(tau, 1e-6))
    y = np.empty_like(x, dtype=float)
    y[0] = x[0] * (1.0 - a)
    y[1:] = x[1:] - a * x[:-1]
    w = 2.0 * np.pi * freq
    gain = 1.0 - a * np.exp(-1j * w * dt)
    return y, gain


# --------------------------------------------------------------------------
# step 4: sliding full / half cycle DFT
# --------------------------------------------------------------------------
@dataclass
class PhasorStream:
    """Per-sample phasor estimates for one record."""

    t: np.ndarray
    freq: float
    fs: float
    n_window: int
    phasors: Dict[str, np.ndarray]
    half_cycle: bool = False
    valid_from: int = 0

    def at(self, name: str, idx: int) -> complex:
        return complex(self.phasors[name][idx])

    def window_indices(self, t0: float, t1: float) -> np.ndarray:
        """Indices whose ENTIRE DFT window lies inside [t0, t1]."""
        dt = 1.0 / self.fs
        lo = t0 + (self.n_window - 1) * dt
        sel = np.nonzero((self.t >= lo) & (self.t <= t1))[0]
        return sel[sel >= self.n_window - 1]


def sliding_dft(
    x: np.ndarray,
    t: np.ndarray,
    fs: float,
    freq: float,
    half_cycle: bool = False,
    tau: Optional[float] = None,
) -> np.ndarray:
    """RMS fundamental phasor per sample, referenced to absolute time."""
    n = int(round(fs / freq))
    if half_cycle:
        n = max(n // 2, 2)
    x = np.asarray(x, dtype=float)
    gain = 1.0 + 0j
    if tau is not None:
        x, gain = mimic_filter(x, fs, freq, tau)
    w = 2.0 * np.pi * freq
    y = x * np.exp(-1j * w * t)
    c = np.concatenate(([0.0 + 0j], np.cumsum(y)))
    out = np.full(x.size, np.nan + 0j, dtype=complex)
    if x.size >= n:
        s = c[n:] - c[:-n]
        out[n - 1 :] = (2.0 / n) * s
    if half_cycle:
        # a half-cycle window leaves the conjugate term uncancelled; the
        # standard correction is to double the odd-harmonic-only estimate
        out = out
    out = out / math.sqrt(2.0)
    return out / gain


def phasors_for(
    rec_t: np.ndarray,
    channels: Dict[str, np.ndarray],
    fs: float,
    freq: float,
    tau: Optional[float] = None,
    half_cycle: bool = False,
) -> PhasorStream:
    n = int(round(fs / freq))
    if half_cycle:
        n = max(n // 2, 2)
    ph = {
        k: sliding_dft(v, rec_t, fs, freq, half_cycle=half_cycle, tau=tau)
        for k, v in channels.items()
    }
    return PhasorStream(
        t=rec_t, freq=freq, fs=fs, n_window=n, phasors=ph,
        half_cycle=half_cycle, valid_from=n - 1,
    )


# --------------------------------------------------------------------------
# step 5: symmetrical components
# --------------------------------------------------------------------------
def sequence(pa: np.ndarray, pb: np.ndarray, pc: np.ndarray):
    """Phasor streams a/b/c -> (zero, positive, negative)."""
    z = (pa + pb + pc) / 3.0
    p = (pa + A * pb + A * A * pc) / 3.0
    n = (pa + A * A * pb + A * pc) / 3.0
    return z, p, n


def add_sequence(ps: PhasorStream) -> PhasorStream:
    """Attach I0/I1/I2 and V0/V1/V2 streams in place."""
    for kind in ("I", "V"):
        a, b, c = kind + "A", kind + "B", kind + "C"
        if all(k in ps.phasors for k in (a, b, c)):
            z, p, n = sequence(ps.phasors[a], ps.phasors[b], ps.phasors[c])
            ps.phasors[kind + "0"] = z
            ps.phasors[kind + "1"] = p
            ps.phasors[kind + "2"] = n
    return ps


# --------------------------------------------------------------------------
# step 6: superimposed quantities
# --------------------------------------------------------------------------
def prefault_reference(
    ps: PhasorStream, inception_idx: int, cycles: float = 2.0
) -> Dict[str, complex]:
    """Steady pre-fault phasor per channel, averaged over a clean window.

    Ends one full DFT window before inception so no fault sample leaks in.
    """
    n = ps.n_window
    hi = inception_idx - n
    lo = max(ps.valid_from, hi - int(round(cycles * ps.fs / ps.freq)))
    ref: Dict[str, complex] = {}
    for k, v in ps.phasors.items():
        if hi <= lo:
            ref[k] = complex(np.nan)
            continue
        seg = v[lo:hi]
        seg = seg[np.isfinite(seg)]
        ref[k] = complex(np.mean(seg)) if seg.size else complex(np.nan)
    return ref


def superimposed(ps: PhasorStream, ref: Dict[str, complex]) -> Dict[str, np.ndarray]:
    """delta = fault phasor - steady pre-fault phasor, per channel."""
    return {k: v - ref.get(k, 0.0 + 0j) for k, v in ps.phasors.items()}
