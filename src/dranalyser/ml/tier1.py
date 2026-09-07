"""Tier 1 - estimate the line's actual parameters. Build this first.

The dominant residual error in impedance-based location is wrong line data,
above all Z0: it is taken from a design calculation, it depends on soil
resistivity, and it is routinely 10-20 % wrong. This is parameter
estimation, not machine learning. It needs a handful of events, not
hundreds, and it improves every subsequent single-ended calculation --
including the one the relay itself performs and reports.

The key move is that the two-ended unsynchronised estimate E5 needs no zero
sequence data at all. So E5 supplies m independently, and k0 becomes the only
unknown in the single-ended ground-loop equation. No ground truth is needed.

Method
------
For a single-phase-to-ground fault, at either terminal:

    V_ph = m*Z1*(I_ph + k0*3*I0) + R_F*I_F

Project onto the superimposed current, which cancels the fault-resistance
term when the system is homogeneous (the Takagi argument):

    Im[ (V_ph - m*Z1*I_ph - m*Z1*k0*3*I0) * conj(I_sup) ] = 0

m is known from E5. Writing k0 = kr + j*ki and
W = m*Z1*3*I0*conj(I_sup), this is linear:

    kr*Im(W) + ki*Re(W) = Im[ (V_ph - m*Z1*I_ph) * conj(I_sup) ]

One real equation per sample per terminal. Least squares over the analysis
window of a few events is well conditioned.

Reference: Wang et al., Algorithms and field experiences for estimating
transmission line parameters based on fault record data, IET GTD (2015).
"""
from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..dsp.pipeline import Analysed
from ..faultloc.estimators import GROUND_LOOP
from ..registry.model import Line, k0_from_impedances


@dataclass
class K0Estimate:
    k0: complex
    k0_registry: complex
    z0_implied: complex
    z0_registry: complex
    n_equations: int
    n_events: int
    residual_rms: float
    condition: float
    z0_error_pct: float
    accepted: bool
    reason: str = ""

    def report(self) -> str:
        L = ["Tier 1 - line parameter estimation from fault records",
             "  events used            : " + str(self.n_events)
             + "   equations: " + str(self.n_equations),
             "  k0 from registry Z0/Z1 : " + format(abs(self.k0_registry), ".4f")
             + " angle " + format(math.degrees(cmath.phase(self.k0_registry)), "+.2f") + " deg",
             "  k0 estimated from data : " + format(abs(self.k0), ".4f")
             + " angle " + format(math.degrees(cmath.phase(self.k0)), "+.2f") + " deg",
             "  Z0 registry            : " + format(self.z0_registry.real, ".4f")
             + " + j" + format(self.z0_registry.imag, ".4f") + " ohm",
             "  Z0 implied by the data : " + format(self.z0_implied.real, ".4f")
             + " + j" + format(self.z0_implied.imag, ".4f") + " ohm",
             "  |Z0| discrepancy       : " + format(self.z0_error_pct, "+.1f") + " %",
             "  fit residual (rms)     : " + format(self.residual_rms, ".4e"),
             "  accepted               : " + ("yes" if self.accepted else "NO - " + self.reason)]
        return "\n".join(L)


@dataclass
class Observation:
    """One incident contributed to the parameter fit."""

    m: float                     # from E5, which uses no zero-sequence data
    fault: str
    terminals: Dict[str, Analysed]
    polarity: Dict[str, int] = field(default_factory=dict)
    weight: float = 1.0


def _rows_for(obs: Observation, line: Line, max_samples: int = 16):
    """Build the least-squares rows for one incident."""
    if obs.fault not in GROUND_LOOP:
        return np.zeros((0, 2)), np.zeros((0,))
    p = GROUND_LOOP[obs.fault]
    z1 = line.z1
    A_rows, b_rows = [], []
    for end, an in obs.terminals.items():
        pol = obs.polarity.get(end, 1)
        idxs = an.indices()
        if idxs.size == 0:
            continue
        if idxs.size > max_samples:
            idxs = idxs[np.linspace(0, idxs.size - 1, max_samples).round().astype(int)]
        # m is measured from S; a terminal at R sees the fault at 1 - m
        mm = obs.m if end == "S" else 1.0 - obs.m
        for i in idxs:
            v = an.phasor("V" + p, i)
            iph = an.phasor("I" + p, i) * pol
            i0 = an.phasor("I0", i) * pol
            isup = iph - an.ref.get("I" + p, 0j) * pol
            if abs(isup) < 1e-9 or abs(i0) < 1e-9:
                continue
            w = mm * z1 * 3.0 * i0 * isup.conjugate()
            rhs = ((v - mm * z1 * iph) * isup.conjugate()).imag
            A_rows.append([w.imag, w.real])
            b_rows.append(rhs)
    return np.asarray(A_rows, dtype=float), np.asarray(b_rows, dtype=float)


def estimate_k0(
    observations: Sequence[Observation],
    line: Line,
    max_change: float = 0.35,
    min_events: int = 2,
) -> K0Estimate:
    """Least-squares complex k0 from a set of confirmed-geometry incidents."""
    k0_reg = k0_from_impedances(line.z1, line.z0)
    A_all, b_all = [], []
    used = 0
    for obs in observations:
        A, b = _rows_for(obs, line)
        if A.size == 0:
            continue
        w = math.sqrt(max(obs.weight, 1e-6))
        A_all.append(A * w)
        b_all.append(b * w)
        used += 1
    if used < min_events or not A_all:
        return K0Estimate(k0=k0_reg, k0_registry=k0_reg, z0_implied=line.z0,
                          z0_registry=line.z0, n_equations=0, n_events=used,
                          residual_rms=float("nan"), condition=float("nan"),
                          z0_error_pct=0.0, accepted=False,
                          reason="need at least " + str(min_events)
                          + " single-phase-to-ground incidents, have " + str(used))
    A = np.vstack(A_all)
    b = np.concatenate(b_all)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cond = float(np.linalg.cond(A))
    resid = float(np.sqrt(np.mean((A @ sol - b) ** 2)) / max(np.sqrt(np.mean(b ** 2)), 1e-12))
    k0 = complex(sol[0], sol[1])
    z0 = line.z1 * (1.0 + 3.0 * k0)
    err = (abs(z0) - abs(line.z0)) / abs(line.z0) * 100.0 if abs(line.z0) else float("nan")

    accepted, why = True, ""
    if not np.isfinite(cond) or cond > 1e8:
        accepted, why = False, "design matrix is ill conditioned (cond = " + format(cond, ".1e") + ")"
    elif abs(k0 - k0_reg) > max_change * abs(k0_reg):
        accepted, why = False, ("estimate moves k0 by "
                                + format(abs(k0 - k0_reg) / abs(k0_reg) * 100.0, ".0f")
                                + " %, beyond the " + format(max_change * 100, ".0f")
                                + " % sanity limit; suspect a ratio or polarity error "
                                "rather than a wrong Z0")
    elif z0.imag <= 0 or z0.real < 0:
        accepted, why = False, "implied Z0 is not physical"

    return K0Estimate(k0=k0, k0_registry=k0_reg, z0_implied=z0, z0_registry=line.z0,
                      n_equations=int(A.shape[0]), n_events=used, residual_rms=resid,
                      condition=cond, z0_error_pct=err, accepted=accepted, reason=why)


def apply_k0(line: Line, est: K0Estimate) -> Line:
    """Return a copy of the line with Z0 replaced by the fitted value.

    Only ever applied when the estimate was accepted, and the original stays
    in the record so a report can print both.
    """
    import copy

    if not est.accepted:
        return line
    out = copy.deepcopy(line)
    scale = est.z0_implied / line.z0
    for s in out.sections:
        z = complex(s.r0, s.x0) * scale
        s.r0, s.x0 = z.real, z.imag
    return out


def estimate_z1_from_ground_truth(
    observations: Sequence[Observation], line: Line,
) -> Optional[complex]:
    """Fit Z1 when patrol has confirmed the true location.

    With m known, the two-ended constraint
        V2S - m*Z1*I2S = (V2R - (1-m)*Z1*I2R) * exp(j*delta)
    has one shared complex unknown Z1 and one nuisance angle per event, so
    two confirmed events determine Z1. Needs the ground_truth table, which is
    the scarcest and most valuable data in the system.
    """
    rows, rhs = [], []
    for obs in observations:
        s = obs.terminals.get("S")
        r = obs.terminals.get("R")
        if s is None or r is None:
            continue
        si, ri = s.indices(), r.indices()
        if si.size == 0 or ri.size == 0:
            continue
        n = min(si.size, ri.size, 8)
        for k in range(n):
            i, j = si[k], ri[k]
            v2s, i2s = s.phasor("V2", i), s.phasor("I2", i)
            v2r, i2r = r.phasor("V2", j), r.phasor("I2", j)
            # magnitude form removes the unknown angle:
            #   |V2S - m*Z1*I2S| = |V2R - (1-m)*Z1*I2R|
            # solved by a small scalar search on |Z1| at the known line angle
            rows.append((obs.m, v2s, i2s, v2r, i2r))
    if len(rows) < 4:
        return None
    ang = cmath.phase(line.z1)
    def cost(mag: float) -> float:
        z = cmath.rect(mag, ang)
        tot = 0.0
        for m, v2s, i2s, v2r, i2r in rows:
            tot += (abs(v2s - m * z * i2s) - abs(v2r - (1.0 - m) * z * i2r)) ** 2
        return tot
    base = abs(line.z1)
    grid = np.linspace(0.6 * base, 1.6 * base, 401)
    vals = [cost(float(g)) for g in grid]
    return cmath.rect(float(grid[int(np.argmin(vals))]), ang)
