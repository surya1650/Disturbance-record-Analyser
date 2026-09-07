"""Fault location estimators E1-E5 (brief section 7).

Every estimator is a pure function of phasors and line parameters. No I/O,
no record objects, no globals. m is per-unit distance from end S, measured
in per-unit of series REACTANCE (see registry.Line.m_to_km).

Corrections applied here relative to the brief, with reasons:

E2  The brief writes  m = Im(V_S*conj(I_sup)) / Im(Z1L*I_S*conj(I_sup)).
    The defining equation is V_loop = m*Z1L*I_loop + R_F*I_F, so the
    denominator must use the COMPENSATED LOOP current, not the raw phase
    current. With raw I_ph the error is of order |k0*3I0 / I_loop|, which on
    a solid single-phase-to-ground fault is tens of percent.

E3  The brief writes exp(-j*beta) and never defines the sign of beta.
    Deriving it: with d = I0_S/I0_F and I_F = 3*I0_S/d, killing the R_F term
    requires multiplying by conj(3*I0_S * exp(-j*beta)) = conj(3*I0_S)*exp(+j*beta)
    where beta = arg(d). The opposite sign applies the homogeneity correction
    backwards, roughly doubling the error it was added to remove.

E4  The brief does not say what to do with the imaginary part of m. It is
    taken as Re(m), and |Im(m)| is returned as a free quality metric: a large
    imaginary part means a ratio error, a polarity error or misalignment.

E5  The brief says only "solve; take the root in [0,1]". The leading
    coefficient is |Z1L|^2*(|I2S|^2 - |I2R|^2), which goes to zero for a
    fault near the electrical midpoint of a line with comparable sources --
    the commonest case, not a corner case. A naive quadratic solve loses
    precision there. Solved with the numerically stable pair, degenerating
    to linear when required, with the root chosen by sync-angle stability
    across the window rather than by the [0,1] test alone.
"""
from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

TWO_PI = 2.0 * math.pi

# loop selection per fault type
GROUND_LOOP = {"AG": "A", "BG": "B", "CG": "C"}
PHASE_LOOP = {
    "AB": ("A", "B"), "ABG": ("A", "B"),
    "BC": ("B", "C"), "BCG": ("B", "C"),
    "CA": ("C", "A"), "CAG": ("C", "A"),
    "ABC": ("A", "B"), "ABCG": ("A", "B"),
}


@dataclass
class Estimate:
    """One estimator's answer for one incident."""

    method: str
    m: float
    residual: float
    ok: bool = True
    reason: str = ""
    ends: str = ""
    diagnostics: Dict[str, float] = field(default_factory=dict)
    spread: Optional[Tuple[float, float]] = None   # 5th / 95th pct over window

    def __str__(self) -> str:
        if not self.ok:
            return self.method + ": n/a (" + self.reason + ")"
        return self.method + ": m=" + format(self.m, ".5f") + " resid=" + format(
            self.residual, ".3e"
        )


def _fail(method: str, reason: str) -> Estimate:
    return Estimate(method=method, m=float("nan"), residual=float("inf"),
                    ok=False, reason=reason)


# --------------------------------------------------------------------------
# loop quantities
# --------------------------------------------------------------------------
def loop_quantities(
    vph: Dict[str, complex], iph: Dict[str, complex], i0: complex,
    k0: complex, fault: str,
) -> Tuple[complex, complex, str]:
    """(V_loop, I_loop, description) for the fault type.

    Ground loop:  V_ph,           I_ph + k0*3*I0
    Phase loop:   V_x - V_y,      I_x - I_y      (no k0, no Z0 -- preferred
                                                  wherever it is available)
    """
    if fault in GROUND_LOOP:
        p = GROUND_LOOP[fault]
        return vph[p], iph[p] + k0 * 3.0 * i0, p + "-G"
    if fault in PHASE_LOOP:
        x, y = PHASE_LOOP[fault]
        return vph[x] - vph[y], iph[x] - iph[y], x + "-" + y
    raise ValueError("no loop defined for fault type " + repr(fault))


# --------------------------------------------------------------------------
# E1 - simple reactance
# --------------------------------------------------------------------------
def e1_reactance(v_loop: complex, i_loop: complex, z1_line: complex) -> Estimate:
    if abs(i_loop) < 1e-9:
        return _fail("E1", "loop current is zero")
    z_app = v_loop / i_loop
    denom = z1_line.imag
    if abs(denom) < 1e-12:
        return _fail("E1", "line reactance is zero")
    m = z_app.imag / denom
    return Estimate(
        method="E1", m=float(m), residual=abs(z_app.real - m * z1_line.real),
        ends="single",
        diagnostics={"z_apparent_r": z_app.real, "z_apparent_x": z_app.imag,
                     "rf_apparent": z_app.real - m * z1_line.real},
    )


# --------------------------------------------------------------------------
# E2 - Takagi
# --------------------------------------------------------------------------
def e2_takagi(
    v_loop: complex, i_loop: complex, i_sup: complex, z1_line: complex
) -> Estimate:
    if abs(i_sup) < 1e-9:
        return _fail("E2", "superimposed current is zero (no clean pre-fault)")
    num = (v_loop * i_sup.conjugate()).imag
    den = (z1_line * i_loop * i_sup.conjugate()).imag
    if abs(den) < 1e-12:
        return _fail("E2", "degenerate denominator")
    m = num / den
    return Estimate(method="E2", m=float(m), residual=abs(den) and abs(num - m * den) / abs(den),
                    ends="single", diagnostics={"i_sup_mag": abs(i_sup)})


# --------------------------------------------------------------------------
# E3 - modified Takagi with homogeneity correction (ground faults only)
# --------------------------------------------------------------------------
def distribution_factor_zero(
    m: float, z0_line: complex, zs0_local: complex, zs0_remote: complex
) -> complex:
    """d0 = I0_local / I0_fault for a fault at m from the local end."""
    den = zs0_local + z0_line + zs0_remote
    if abs(den) < 1e-12:
        return 1.0 + 0j
    return (zs0_remote + (1.0 - m) * z0_line) / den


def e3_modified_takagi(
    v_loop: complex, i_loop: complex, i0: complex, z1_line: complex,
    z0_line: complex, zs0_local: complex, zs0_remote: complex,
    m_seed: float = 0.5, iterations: int = 4,
) -> Estimate:
    """Ground faults only. beta = arg(d0); the reference current is rotated
    by exp(+j*beta), which is what cancels the R_F term."""
    i_ref = 3.0 * i0
    if abs(i_ref) < 1e-9:
        return _fail("E3", "no zero-sequence current (not a ground fault)")
    m = float(m_seed)
    beta = 0.0
    for _ in range(iterations):
        d0 = distribution_factor_zero(m, z0_line, zs0_local, zs0_remote)
        beta = cmath.phase(d0)
        rot = i_ref.conjugate() * cmath.exp(1j * beta)
        num = (v_loop * rot).imag
        den = (z1_line * i_loop * rot).imag
        if abs(den) < 1e-12:
            return _fail("E3", "degenerate denominator")
        m_new = num / den
        if abs(m_new - m) < 1e-9:
            m = m_new
            break
        m = m_new
    return Estimate(method="E3", m=float(m), residual=0.0, ends="single",
                    diagnostics={"beta_deg": math.degrees(beta)})


# --------------------------------------------------------------------------
# E4 - two-ended synchronised
# --------------------------------------------------------------------------
def e4_synchronised(
    v2s: complex, i2s: complex, v2r: complex, i2r: complex, z1_line: complex
) -> Estimate:
    """m = (V2S - V2R + Z1L*I2R) / (Z1L*(I2S + I2R)).

    Both currents must be positive from bus INTO the line. Requires the two
    phasors to share a time reference, i.e. good clock quality at both ends.
    """
    den = z1_line * (i2s + i2r)
    if abs(den) < 1e-9:
        return _fail("E4", "I2S + I2R is zero (no negative sequence)")
    mc = (v2s - v2r + z1_line * i2r) / den
    return Estimate(
        method="E4", m=float(mc.real), residual=abs(mc.imag), ends="two",
        diagnostics={"m_imag": mc.imag, "m_imag_abs": abs(mc.imag)},
    )


# --------------------------------------------------------------------------
# E5 - two-ended unsynchronised
# --------------------------------------------------------------------------
def stable_quadratic(a: float, b: float, c: float) -> Tuple[List[float], str]:
    """Roots of a*m^2 + b*m + c, without the cancellation of the naive form."""
    scale = max(abs(b), abs(c), 1e-300)
    if abs(a) < 1e-12 * scale:
        if abs(b) < 1e-300:
            return [], "degenerate: a and b both vanish"
        return [-c / b], "linear (near-degenerate leading coefficient)"
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return [-b / (2.0 * a)], "no real root; vertex returned"
    sq = math.sqrt(disc)
    q = -0.5 * (b + math.copysign(sq, b if b != 0.0 else 1.0))
    roots = [q / a]
    if abs(q) > 1e-300:
        roots.append(c / q)
    return sorted(set(roots)), "quadratic"


def e5_terms(v2s: complex, i2s: complex, v2r: complex, i2r: complex,
             z1_line: complex) -> Tuple[complex, complex, complex, complex]:
    """A, B, C, D such that the constraint is |A - m*B| = |C + m*D|."""
    a = v2s
    b = z1_line * i2s
    c = v2r - z1_line * i2r
    d = z1_line * i2r
    return a, b, c, d


def e5_roots(v2s: complex, i2s: complex, v2r: complex, i2r: complex,
             z1_line: complex) -> Tuple[List[float], Dict[str, float], str]:
    A, B, C, D = e5_terms(v2s, i2s, v2r, i2r, z1_line)
    a = abs(B) ** 2 - abs(D) ** 2
    b = -2.0 * ((A * B.conjugate()).real + (C * D.conjugate()).real)
    c = abs(A) ** 2 - abs(C) ** 2
    roots, how = stable_quadratic(a, b, c)
    cond = abs(a) / max(abs(b), abs(c), 1e-300)
    return roots, {"a": a, "b": b, "c": c, "conditioning": cond}, how


def e5_delta(m: float, v2s: complex, i2s: complex, v2r: complex,
             i2r: complex, z1_line: complex) -> float:
    """Recovered synchronisation angle, radians, wrapped to (-pi, pi]."""
    left = v2s - m * z1_line * i2s
    right = v2r - (1.0 - m) * z1_line * i2r
    if abs(left) < 1e-12 or abs(right) < 1e-12:
        return float("nan")
    d = cmath.phase(left) - cmath.phase(right)
    return (d + math.pi) % TWO_PI - math.pi


def e5_residual(m: float, v2s: complex, i2s: complex, v2r: complex,
                i2r: complex, z1_line: complex) -> float:
    A, B, C, D = e5_terms(v2s, i2s, v2r, i2r, z1_line)
    left, right = abs(A - m * B), abs(C + m * D)
    denom = max(left, right, 1e-12)
    return abs(left - right) / denom


def _circ_std(angles: Sequence[float]) -> float:
    a = np.asarray([x for x in angles if np.isfinite(x)], dtype=float)
    if a.size < 2:
        return float("inf")
    r = abs(np.mean(np.exp(1j * a)))
    r = min(max(r, 1e-12), 1.0)
    return float(math.sqrt(-2.0 * math.log(r)))


def e5_unsynchronised(
    v2s: Sequence[complex], i2s: Sequence[complex],
    v2r: Sequence[complex], i2r: Sequence[complex],
    z1_line: complex, prefer_unit_interval: bool = True,
) -> Estimate:
    """Two-ended unsynchronised location over a window of samples.

    Root selection: the physically correct root gives a recovered sync angle
    that is CONSTANT across the analysis window (the two clocks do not drift
    measurably in 1-2 cycles). The spurious root gives an angle that wanders.
    That test needs no clock, no timestamps and no GPS, which is the whole
    point of E5, unlike the timestamp comparison the brief proposes.
    """
    n = min(len(v2s), len(i2s), len(v2r), len(i2r))
    if n == 0:
        return _fail("E5", "empty analysis window")

    per_sample: List[List[float]] = []
    conds: List[float] = []
    how_last = ""
    for k in range(n):
        roots, diag, how = e5_roots(v2s[k], i2s[k], v2r[k], i2r[k], z1_line)
        per_sample.append(roots)
        conds.append(diag["conditioning"])
        how_last = how
    flat = [r for rs in per_sample for r in rs]
    if not flat:
        return _fail("E5", "no real root at any sample")

    # candidate branches: low root and high root, taken as medians
    lows = [min(rs) for rs in per_sample if rs]
    highs = [max(rs) for rs in per_sample if rs]
    candidates = []
    for label, seq in (("low", lows), ("high", highs)):
        if not seq:
            continue
        med = float(np.median(seq))
        deltas, ms = [], []
        for k in range(n):
            if not per_sample[k]:
                continue
            r = min(per_sample[k], key=lambda x: abs(x - med))
            ms.append(r)
            deltas.append(e5_delta(r, v2s[k], i2s[k], v2r[k], i2r[k], z1_line))
        if not ms:
            continue
        candidates.append({
            "label": label,
            "m": float(np.median(ms)),
            "ms": ms,
            "delta_std": _circ_std(deltas),
            "delta": float(np.angle(np.mean(np.exp(1j * np.asarray(deltas))))),
        })
    if not candidates:
        return _fail("E5", "no usable root branch")

    def score(c):
        inside = 0.0 <= c["m"] <= 1.0
        penalty = 0.0 if (inside or not prefer_unit_interval) else 1.0
        return (penalty, c["delta_std"])

    best = min(candidates, key=score)
    other = [c for c in candidates if c is not best]

    # A root far outside the line is not a location, it is evidence that the
    # inputs are inconsistent -- a saturated CT, a wrong ratio, a reversed
    # polarity. Returning it as a number invites someone to believe the fault
    # was six line lengths away, so E5 declines instead.
    if not (-0.5 <= best["m"] <= 1.5):
        return _fail("E5", "no root near the line (best root m = "
                     + format(best["m"], ".2f") + "); the two terminals disagree "
                     "beyond what a fault location can explain - check CT "
                     "saturation, CT/VT ratios and polarity")

    ms = np.asarray(best["ms"], dtype=float)
    resid = float(np.median([
        e5_residual(best["m"], v2s[k], i2s[k], v2r[k], i2r[k], z1_line)
        for k in range(n)
    ]))
    lo, hi = (float(np.percentile(ms, 5)), float(np.percentile(ms, 95))) if ms.size > 2 else (
        float(ms.min()), float(ms.max())
    )
    diag = {
        "delta_deg": math.degrees(best["delta"]),
        "delta_std_deg": math.degrees(best["delta_std"]),
        "branch": 0.0 if best["label"] == "low" else 1.0,
        "conditioning_median": float(np.median(conds)),
        "n_samples": float(n),
        "root_separation": abs(best["m"] - other[0]["m"]) if other else float("nan"),
        "window_spread": float(hi - lo),
    }
    return Estimate(method="E5", m=best["m"], residual=resid, ends="two",
                    reason=how_last, diagnostics=diag, spread=(lo, hi))
