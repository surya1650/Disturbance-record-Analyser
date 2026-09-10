"""Runs the whole section-6 chain over one Record and caches the results.

Note on resampling (section 6 step 1): the estimators in faultloc do NOT need
the two records placed on a common sample grid. Because phasors are estimated
against each record's own absolute time origin, a phasor can be evaluated at
whatever instant is wanted at each terminal independently, at that terminal's
native rate. Resampling is therefore only needed for time-domain overlay
plots, where interpolation error is cosmetic rather than propagating into the
location estimate. resample_to() is provided for that purpose only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..signals import PHASE_CURRENTS, PHASE_VOLTAGES, Record
from .core import (PhasorStream, add_sequence, phasors_for, prefault_reference,
                   track_frequency)
from .detect import (AnalysisWindow, Inception, Saturation, classify_fault,
                     detect_clipping, detect_inception, detect_saturation,
                     select_window)

CB_OPEN_NAMES = ("CB_OPEN", "52A", "POLE_OPEN", "ANY POLE DEAD", "Any Pole Dead")


@dataclass
class Analysed:
    """Everything the estimators and the rules engine need from one record."""

    record: Record
    freq: float
    ps: PhasorStream
    ref: Dict[str, complex]
    inception: Optional[Inception]
    fault_type: str
    fault_diag: Dict[str, float]
    saturation: Saturation
    clipping: List[str]
    window: AnalysisWindow
    t_open: Optional[float]
    t_trip: Optional[float]
    tau: float
    # False when the VT set does not pass zero sequence (delta or open-delta
    # secondary). The ground-loop voltage V_ph is then missing V0 and every
    # single-ended ground-fault calculation from this terminal is wrong.
    # Negative-sequence E5 and the phase-phase loops are unaffected.
    zero_seq_voltage: bool = True
    notes: Dict[str, object] = field(default_factory=dict)

    @property
    def end(self) -> str:
        return self.record.terminal_end

    def indices(self) -> np.ndarray:
        """Samples whose whole DFT window sits inside the analysis window."""
        return self.ps.window_indices(self.window.t_start, self.window.t_end)

    def phasor(self, name: str, idx: int) -> complex:
        return complex(self.ps.phasors[name][idx])

    def superimposed(self, name: str, idx: int) -> complex:
        return complex(self.ps.phasors[name][idx]) - self.ref.get(name, 0j)

    def abs_time(self, idx: int):
        return self.record.absolute_time(float(self.ps.t[idx]))

    def index_at(self, t_local: float) -> int:
        return int(np.argmin(np.abs(self.ps.t - t_local)))


def _find_cb_open(rec: Record, inception_t: float) -> Optional[float]:
    """Breaker opening from a digital channel, else from current collapse."""
    for nm in rec.digital:
        override = rec.notes.get('digital_overrides', {}).get(nm)
        if override is not None:
            if override in ('CB_OPEN_A', 'CB_OPEN_B', 'CB_OPEN_C', 'ANY_POLE_DEAD', 'ALL_POLE_DEAD'):
                t = rec.first_assert(nm)
                if t is not None and t > inception_t:
                    return t
            continue
        if nm.strip().upper().replace("-", "_") in [
            c.upper().replace("-", "_") for c in CB_OPEN_NAMES
        ] or "OPEN" in nm.upper() or "POLE DEAD" in nm.upper():
            t = rec.first_assert(nm)
            if t is not None and t > inception_t:
                return t
    # fallback: envelope of phase currents collapsing
    n = int(round(rec.fs / rec.line_freq))
    amp = None
    for k in PHASE_CURRENTS:
        x = rec.analog.get(k)
        if x is None:
            continue
        env = np.abs(x)
        env = np.convolve(env, np.ones(n) / n, mode="same")
        amp = env if amp is None else np.maximum(amp, env)
    if amp is None:
        return None
    i0 = int(np.argmin(np.abs(rec.t - inception_t)))
    peak = float(np.max(amp[i0 : i0 + 6 * n])) if i0 + n < amp.size else 0.0
    if peak <= 0:
        return None
    tail = np.nonzero(amp[i0 + n :] < 0.10 * peak)[0]
    return float(rec.t[i0 + n + tail[0]]) if tail.size else None


def _find_trip(rec: Record) -> Optional[float]:
    reviewed = rec.notes.get('digital_overrides', {})
    cands = [nm for nm in rec.digital if ('TRIP' in reviewed[nm] if nm in reviewed else 'TRIP' in nm.upper())]
    times = [rec.first_assert(nm) for nm in cands]
    times = [t for t in times if t is not None]
    return min(times) if times else None


def analyse(
    rec: Record,
    xr_ratio: float = 15.0,
    vt_type: str = "CVT",
    half_cycle: Optional[bool] = None,
    t_open_remote: Optional[float] = None,
) -> Analysed:
    """Full section-6 chain for one record."""
    freq_nom = rec.line_freq
    va = rec.analog.get("VA")
    n_pre = int(round(rec.fs / freq_nom)) * 4
    freq = track_frequency(va, rec.fs, freq_nom, upto=n_pre) if va is not None else freq_nom

    tau = xr_ratio / (2.0 * math.pi * freq)

    inc = detect_inception(rec.analog, rec.t, rec.fs, freq)
    inception_t = inc.t_refined if inc else float(rec.t[0])

    chans = {k: rec.analog[k] for k in (PHASE_CURRENTS + PHASE_VOLTAGES) if k in rec.analog}
    if "IN" in rec.analog:
        chans["IN"] = rec.analog["IN"]
    ps = add_sequence(phasors_for(rec.t, chans, rec.fs, freq, tau=tau,
                                  half_cycle=bool(half_cycle)))

    ref = prefault_reference(ps, inc.idx if inc else ps.valid_from + 1)

    t_open = _find_cb_open(rec, inception_t)
    t_trip = _find_trip(rec)

    win = select_window(inception_t, freq, t_open, t_open_remote,
                        float(rec.t[-1]), vt_type=vt_type)

    # classify at the middle of the usable window, or just after blanking
    t_cls = 0.5 * (win.t_start + win.t_end) if win.t_end > win.t_start else win.t_start
    icls = int(np.argmin(np.abs(ps.t - t_cls)))
    icls = max(icls, ps.valid_from)
    ftype, fdiag = classify_fault(
        complex(ps.phasors["I1"][icls]),
        complex(ps.phasors["I2"][icls]),
        complex(ps.phasors["I0"][icls]),
        ref.get("I1", 0j),
    )

    # Saturation is looked for strictly between the inception step and the
    # breaker opening. Both of those are genuine discontinuities and would
    # otherwise be read as saturation by a third-difference detector.
    spc = rec.fs / freq
    i_lo = int((inc.idx if inc else ps.valid_from) + 0.25 * spc)
    i_hi = int(np.argmin(np.abs(ps.t - win.t_end))) if win.t_end > win.t_start else ps.t.size
    i_hi = min(i_hi, ps.t.size)
    sat = detect_saturation(rec.analog, rec.fs, freq, i_lo, max(i_hi, i_lo + 8))
    clip = detect_clipping(rec.raw_analog or {}, rec.analog_meta)

    # Zero-sequence voltage sanity. A ground fault drawing real 3I0 must
    # produce real 3V0 at the terminal. If it does not, the VT secondary is
    # delta / open-delta and cannot pass zero sequence, so the phase voltage
    # in the ground loop is missing V0. Detected on the real Main-1 record in
    # this repo: 575 V of V0 against 1670 A of I0, while the other relay in
    # the same bay saw 34 kV. Not repaired -- reported, and the affected
    # estimators are gated off downstream.
    zs_ok = True
    i0m, i1m = abs(ps.phasors["I0"][icls]), abs(ps.phasors["I1"][icls])
    v0m = abs(ps.phasors["V0"][icls])
    v1pre = abs(ref.get("V1", 0j))
    if np.isfinite(i0m) and np.isfinite(v0m) and v1pre > 0 and i1m > 0:
        if i0m > 0.10 * i1m and v0m < 0.02 * v1pre:
            zs_ok = False
            rec.add_flag(
                "VT-NO-ZERO", "flag",
                "the VT set does not pass zero sequence: |V0| is "
                + format(v0m, ".0f") + " V while |I0| is " + format(i0m, ".0f")
                + " A. The secondary is delta or open-delta, so the phase "
                "voltage is missing V0 and single-ended GROUND-loop location "
                "from this terminal would be wrong. Phase-phase loops and the "
                "two-ended negative-sequence method E5 are unaffected.",
                v0=v0m, i0=i0m, v1_prefault=v1pre)

    return Analysed(
        record=rec, freq=freq, ps=ps, ref=ref, inception=inc,
        fault_type=ftype, fault_diag=fdiag, saturation=sat, clipping=clip,
        window=win, t_open=t_open, t_trip=t_trip, tau=tau,
        zero_seq_voltage=zs_ok,
        notes={"classify_idx": icls, "inception_t": inception_t},
    )


def resample_to(x: np.ndarray, fs_in: float, fs_out: float) -> np.ndarray:
    """Band-limited resampling, for time-domain overlay plots only.

    Linear interpolation adds amplitude error; polyphase resampling does not.
    """
    from fractions import Fraction

    from scipy.signal import resample_poly

    fr = Fraction(fs_out / fs_in).limit_denominator(1000)
    return resample_poly(np.asarray(x, dtype=float), fr.numerator, fr.denominator)
