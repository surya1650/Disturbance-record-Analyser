"""Detection and classification, steps 7-11 of the brief's section 6."""
from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .core import PhasorStream

GROUND_TYPES = ("AG", "BG", "CG", "ABG", "BCG", "CAG")
PHASE_TYPES = ("AB", "BC", "CA")
THREE_PHASE = ("ABC",)

# SEL-style fault-type selection: the angle of I2 relative to the
# superimposed I1 falls in one of six 60-degree sectors.
_SECTOR = {
    0: ("AG", "BC"),
    60: ("CG", "AB"),
    120: ("BG", "CA"),
    180: ("AG", "BC"),
    240: ("CG", "AB"),
    300: ("BG", "CA"),
}


@dataclass
class Inception:
    idx: int
    t: float
    t_refined: float
    confidence: float


@dataclass
class Saturation:
    detected: bool
    channels: List[str] = field(default_factory=list)
    severity: float = 0.0


@dataclass
class AnalysisWindow:
    """The interval in which phasors are trustworthy (section 6.1)."""

    t_start: float
    t_end: float
    cycles: float
    mode: str            # "full" | "half" | "single_ended_only" | "none"
    reason: str = ""

    @property
    def usable(self) -> bool:
        return self.mode in ("full", "half")


# --------------------------------------------------------------------------
# step 7: inception detection
# --------------------------------------------------------------------------
def detect_inception(
    currents: Dict[str, np.ndarray], t: np.ndarray, fs: float, freq: float,
    rel_threshold: float = 0.20, noise_margin: float = 5.0, persistence: int = 3,
) -> Optional[Inception]:
    """Change detector on the one-cycle-delta of current, sub-sample refined.

    The threshold is the larger of a fixed fraction of the record's peak
    delta and a multiple of the observed pre-fault delta. A purely
    noise-referenced threshold trips on ADC quantisation, which on real
    records is a whole LSB of a range scaled for fault current, not for load
    (measured on this repo's corpus: pre-fault load is ~16 counts).

    Sample-quantised inception costs the relay-operating-time measurement, so
    the threshold crossing is interpolated to sub-sample resolution.
    """
    n = int(round(fs / freq))
    names = [k for k in ("IA", "IB", "IC") if k in currents]
    if not names or t.size < 4 * n:
        return None
    d = np.zeros(t.size)
    for k in names:
        x = np.asarray(currents[k], dtype=float)
        dd = np.abs(x - np.roll(x, n))
        dd[:n] = 0.0
        d = np.maximum(d, dd)

    dmax = float(np.max(d))
    if dmax <= 0.0:
        return None
    base_hi = float(np.max(d[n : 3 * n])) if d.size > 3 * n else 0.0
    thr = max(rel_threshold * dmax, noise_margin * base_hi)
    if thr >= dmax:
        return None

    above = d > thr
    # Stage 1, coarse: first index where the excursion persists, so a single
    # noisy sample or one quantisation step cannot declare a fault.
    coarse = None
    run = 0
    for i in range(n, above.size):
        run = run + 1 if above[i] else 0
        if run >= persistence:
            coarse = i - persistence + 1
            break
    if coarse is None:
        return None

    # Stage 2, fine: a threshold set at a fraction of the PEAK delta is
    # crossed well after the fault actually starts, because the fault current
    # takes time to build. Walk back from the coarse hit to the last sample
    # that still looked like pre-fault. Without this the inception is biased
    # late by several milliseconds, and by a different amount at each
    # terminal because the bias depends on the sample rate -- which destroys
    # the relay-operating-time measurement and the two-ended window overlap.
    fine = max(noise_margin * base_hi, 0.02 * dmax)
    lo = max(n, coarse - int(round(1.5 * n)))
    idx = coarse
    for i in range(coarse, lo - 1, -1):
        if d[i] <= fine:
            idx = min(i + 1, coarse)
            break
    else:
        idx = lo

    i = int(idx)
    thr = fine
    if i > 0 and d[i] != d[i - 1]:
        frac = (thr - d[i - 1]) / (d[i] - d[i - 1])
        frac = min(max(frac, 0.0), 1.0)
    else:
        frac = 0.0
    t_ref = float(t[i - 1] + frac * (t[i] - t[i - 1])) if i > 0 else float(t[i])
    conf = float(min(dmax / max(thr, 1e-12), 100.0))
    return Inception(idx=i, t=float(t[i]), t_refined=t_ref, confidence=conf)


# --------------------------------------------------------------------------
# step 8: fault type classification
# --------------------------------------------------------------------------
def classify_fault(
    i1: complex, i2: complex, i0: complex, i1_pre: complex = 0j,
    r_ground: float = 0.10, r_unbalance: float = 0.10,
) -> Tuple[str, Dict[str, float]]:
    """Fault type from sequence ratios and the I2 / superimposed-I1 angle.

    The relay's own fault-type flag is not trusted: misclassification under
    weak infeed is a documented cause of grossly wrong locations.
    """
    # A degenerate window, or a record whose pre-fault reference could not be
    # formed, produces non-finite phasors. Classifying those crashes on the
    # sector arithmetic; declining to classify is the correct answer and lets
    # the caller report "not classified" rather than dying.
    if not all(cmath.isfinite(z) for z in (i1, i2, i0, i1_pre)):
        return "NONE", {"r2": 0.0, "r0": 0.0, "angle": 0.0}
    di1 = i1 - i1_pre
    m1 = abs(di1)
    if m1 < 1e-9:
        return "NONE", {"r2": 0.0, "r0": 0.0, "angle": 0.0}
    r2, r0 = abs(i2) / m1, abs(i0) / m1
    ratio = i2 / di1
    if not cmath.isfinite(ratio):
        return "NONE", {"r2": r2, "r0": r0, "angle": 0.0}
    ang = (math.degrees(math.atan2(ratio.imag, ratio.real))) % 360.0
    if not math.isfinite(ang):
        return "NONE", {"r2": r2, "r0": r0, "angle": 0.0}
    diag = {"r2": r2, "r0": r0, "angle": ang}

    if r2 < r_unbalance and r0 < r_unbalance:
        return "ABC", diag

    sector = int(round(ang / 60.0) * 60) % 360
    slg, pp = _SECTOR[sector]
    grounded = r0 > r_ground

    # Within a sector the single-phase and phase-phase candidates are 180
    # degrees apart in I2/I1; pick by how much zero sequence there is.
    if grounded and r0 > 0.5 * r2:
        # a genuine single-phase-to-ground fault has r0 ~ r2
        if abs(r0 - r2) < 0.6 * max(r0, r2):
            return slg, diag
        return (pp + "G"), diag
    if grounded:
        return (pp + "G"), diag
    return pp, diag


def faulted_phases(kind: str) -> List[str]:
    if kind in ("NONE",):
        return []
    base = kind[:-1] if kind.endswith("G") and len(kind) > 2 else kind
    if kind in ("AG", "BG", "CG"):
        base = kind[0]
    if kind == "ABC":
        base = "ABC"
    return list(base)


# --------------------------------------------------------------------------
# step 9: CT saturation
# --------------------------------------------------------------------------
def detect_saturation(
    currents: Dict[str, np.ndarray], fs: float, freq: float,
    lo: int, hi: int, k: float = 6.0,
) -> Saturation:
    """Third-difference discontinuity detector over the fault window.

    A pure sinusoid of amplitude X sampled at N per cycle has a bounded third
    difference, X*(2*sin(pi/N))**3. Saturation puts sharp corners in the
    waveform, which the third difference exposes far more clearly than any
    amplitude test.
    """
    n = max(int(round(fs / freq)), 4)
    bound_factor = (2.0 * math.sin(math.pi / n)) ** 3
    hits, sev = [], 0.0
    for name in ("IA", "IB", "IC"):
        x = currents.get(name)
        if x is None or hi - lo < 8:
            continue
        seg = np.asarray(x[lo:hi], dtype=float)
        if seg.size < 8:
            continue
        d3 = seg[3:] - 3.0 * seg[2:-1] + 3.0 * seg[1:-2] - seg[:-3]
        amp = float(np.max(np.abs(seg)))
        if amp <= 0:
            continue
        expect = max(amp * bound_factor, 1e-12)
        ratio = float(np.max(np.abs(d3))) / expect
        if ratio > k:
            hits.append(name)
            sev = max(sev, ratio / k)
    return Saturation(detected=bool(hits), channels=hits, severity=sev)


def detect_clipping(
    raw: Dict[str, np.ndarray], meta: Dict[str, object], tol: float = 0.999
) -> List[str]:
    """ADC clipping, which is a different defect from magnetic saturation.

    The CFG carries per-channel min/max; samples pegged there are clipped.
    Nothing in the brief's section 5.1 checks this.
    """
    out = []
    for name, x in raw.items():
        m = meta.get(name)
        if m is None:
            continue
        lo = getattr(m, "adc_min", None)
        hi = getattr(m, "adc_max", None)
        if lo is None or hi is None:
            continue
        x = np.asarray(x, dtype=float)
        n_hi = int(np.sum(x >= hi * tol))
        n_lo = int(np.sum(x <= lo * tol))
        if n_hi + n_lo >= 3:
            out.append(name)
    return out


# --------------------------------------------------------------------------
# steps 10-11: CVT blanking and analysis window selection
# --------------------------------------------------------------------------
def select_window(
    inception_t: float, freq: float,
    t_open_local: Optional[float], t_open_remote: Optional[float],
    record_end_t: float, vt_type: str = "CVT",
    blank_cycles: float = 1.5, guard_cycles: float = 0.5,
) -> AnalysisWindow:
    """Section 6.1 window selection.

    t_start = inception + 1.5 cycles   (CVT subsidence + CT transient)
    t_end   = min(open_S, open_R) - 0.5 cycle

    A magnetic VT does not have a subsidence transient, so the blanking
    shrinks to a quarter cycle for the CT transient alone.
    """
    cyc = 1.0 / freq
    blank = blank_cycles if vt_type.upper() == "CVT" else 0.25
    t_start = inception_t + blank * cyc
    opens = [x for x in (t_open_local, t_open_remote) if x is not None]
    t_end = (min(opens) - guard_cycles * cyc) if opens else record_end_t
    t_end = min(t_end, record_end_t)
    span = (t_end - t_start) / cyc
    if span >= 1.0:
        mode, reason = "full", "full-cycle DFT, " + format(span, ".2f") + " cycles available"
    elif span >= 0.5:
        mode, reason = "half", "reduced to half-cycle DFT, only " + format(span, ".2f") + " cycles"
    elif span > 0.0:
        mode, reason = "single_ended_only", "under half a cycle of overlap"
    else:
        mode, reason = "none", "no usable fault data before clearing"
    return AnalysisWindow(t_start=t_start, t_end=t_end, cycles=span, mode=mode, reason=reason)


def overlap_window(a: AnalysisWindow, b: AnalysisWindow, freq: float,
                   shift_b: float = 0.0) -> AnalysisWindow:
    """Intersection of two terminals' windows, b shifted onto a's time base."""
    t0 = max(a.t_start, b.t_start + shift_b)
    t1 = min(a.t_end, b.t_end + shift_b)
    span = (t1 - t0) * freq
    if span >= 1.0:
        mode, reason = "full", "two-ended overlap " + format(span, ".2f") + " cycles"
    elif span >= 0.5:
        mode, reason = "half", "two-ended overlap only " + format(span, ".2f") + " cycles"
    elif span > 0:
        mode, reason = "single_ended_only", "two-ended overlap under half a cycle"
    else:
        mode, reason = "none", "no two-ended overlap"
    return AnalysisWindow(t_start=t0, t_end=t1, cycles=span, mode=mode, reason=reason)
