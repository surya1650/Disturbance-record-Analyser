"""E6 - ensemble reconciliation, and the single/double-ended entry point.

Single-ended and double-ended are ONE code path, not two. locate() takes
whatever terminals are present and gates each estimator on what the data can
actually support. That is the only way the brief's section 5.2 behaviour --
issue a single-ended report now, re-issue a corrected two-ended report when
the far-end record lands late -- works without a second implementation.

Convention: m is always per-unit from end S. An estimator run at the R
terminal measures distance from R, so its result is mapped as m_S = 1 - m_R.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..dsp.detect import overlap_window
from ..dsp.pipeline import Analysed
from ..registry.model import Line, Tower, k0_from_impedances
from .estimators import (Estimate, e1_reactance, e2_takagi, e3_modified_takagi,
                         e4_synchronised, e5_unsynchronised, loop_quantities)

SLG = ("AG", "BG", "CG")

# Prior accuracy by method, as 1-sigma per-unit error. Section 7.4 of the
# brief, converted to weights. Replaced by measured back-test priors once the
# archive exists.
PRIOR_SIGMA = {"E1": 0.030, "E2": 0.020, "E3": 0.015, "E4": 0.004, "E5": 0.005}


@dataclass
class TerminalInput:
    """One analysed record plus the registry facts about its terminal."""

    analysed: Analysed
    end: str
    zs1: complex = 0j
    zs0: complex = 0j
    clock_good: bool = False
    polarity: int = 1

    @property
    def sat(self) -> bool:
        return self.analysed.saturation.detected


@dataclass
class LocationResult:
    m: float
    km_from_S: float
    km_from_R: float
    interval_pu: Tuple[float, float]
    interval_km: Tuple[float, float]
    method: str
    mode: str                       # "two-ended" | "single-ended" | "none"
    fault_type: str
    estimates: List[Estimate] = field(default_factory=list)
    towers: List[Tower] = field(default_factory=list)
    likely_tower: Optional[Tower] = None
    diagnostics: Dict[str, object] = field(default_factory=dict)
    caveats: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.mode != "none" and math.isfinite(self.m)

    def table(self) -> str:
        w = ["method  ends     m        km from S    residual    weight   note"]
        w.append("-" * 78)
        for e in self.estimates:
            weight = e.diagnostics.get("weight", float("nan"))
            if e.ok:
                w.append(
                    format(e.method, "<7") + " " + format(e.ends or "-", "<8")
                    + format(e.m, "8.5f") + "  " + format(self._km(e.m), "9.3f")
                    + "   " + format(e.residual, "9.3e") + "  "
                    + format(weight, "7.3f") + "  " + (e.reason or "")
                )
            else:
                w.append(format(e.method, "<7") + " " + format(e.ends or "-", "<8")
                         + "   n/a                              -        " + e.reason)
        return "\n".join(w)

    def _km(self, m: float) -> float:
        return self.diagnostics.get("_km_fn", lambda x: float("nan"))(m)


def _pick(idxs: np.ndarray, n: int) -> np.ndarray:
    """Evenly spaced subset of window indices, at most n of them."""
    if idxs.size <= n:
        return idxs
    sel = np.linspace(0, idxs.size - 1, n).round().astype(int)
    return idxs[sel]


def _fault_consensus(terms: Sequence[TerminalInput]) -> Tuple[str, List[str], bool]:
    """Reconcile the two terminals' fault-type calls.

    Returns (kind, caveats, cross_country). A plain disagreement is NOT a
    cross-country fault: under weak infeed one terminal sees too little
    negative sequence and falls through to the three-phase branch. Only two
    confident, incompatible single-phase-to-ground calls are FT-02, and only
    that case suppresses the two-ended answer.
    """
    calls = [(t.end, t.analysed.fault_type, t.analysed.fault_diag) for t in terms]
    kinds = {k for _, k, _ in calls}
    caveats: List[str] = []
    if len(kinds) == 1:
        return calls[0][1], caveats, False

    unbalanced = [(e, k, d) for e, k, d in calls if k not in ("ABC", "ABCG", "NONE")]
    if len(unbalanced) < len(calls):
        if unbalanced:
            pick = max(unbalanced, key=lambda c: c[2].get("r2", 0.0))
            caveats.append(
                "fault type differs between terminals ("
                + ", ".join(e + "=" + k for e, k, _ in calls)
                + "); taking " + pick[1] + " from end " + pick[0]
                + " which sees the larger negative sequence (weak infeed at the other end)"
            )
            return pick[1], caveats, False
        return calls[0][1], caveats, False

    slg = [(e, k, d) for e, k, d in unbalanced if k in SLG]
    if len(slg) == len(calls) and len({k for _, k, _ in slg}) > 1:
        caveats.append(
            "FT-02 cross-country fault: ground faults on different phases at the "
            "two ends (" + ", ".join(e + "=" + k for e, k, _ in slg)
            + "); two-ended location is meaningless and is suppressed"
        )
        return slg[0][1], caveats, True

    pick = max(unbalanced, key=lambda c: c[2].get("r2", 0.0))
    caveats.append(
        "fault type differs between terminals ("
        + ", ".join(e + "=" + k for e, k, _ in calls) + "); taking " + pick[1]
        + " from end " + pick[0]
    )
    return pick[1], caveats, False


def _single_ended(ti: TerminalInput, line: Line, fault: str) -> List[Estimate]:
    """E1/E2/E3 at one terminal, median over the analysis window."""
    an = ti.analysed
    idxs = _pick(an.indices(), 24)
    if idxs.size == 0:
        return [Estimate(method=m, m=float("nan"), residual=float("inf"), ok=False,
                         reason="no usable analysis window", ends="single")
                for m in ("E1", "E2", "E3")]

    # A ground loop needs the true phase-to-neutral voltage. If this
    # terminal's VT cannot pass zero sequence the loop voltage is missing V0,
    # and E1/E2/E3 would return a confident, wrong number. Refuse instead.
    if fault in SLG and not an.zero_seq_voltage:
        why = ("gated: VT does not pass zero sequence, so the ground-loop "
               "voltage is missing V0 at this terminal")
        return [Estimate(method=m, m=float("nan"), residual=float("inf"), ok=False,
                         reason=why, ends="single") for m in ("E1", "E2", "E3")]

    k0 = k0_from_impedances(line.z1, line.z0)
    z1, z0 = line.z1, line.z0
    far = "R" if ti.end == "S" else "S"
    zs0_far = line.terminals[far].zs0 if far in line.terminals else ti.zs0

    m1, m2, m3 = [], [], []
    d1: Dict[str, float] = {}
    for i in idxs:
        vph = {p: an.phasor("V" + p, i) for p in "ABC"}
        iph = {p: an.phasor("I" + p, i) * ti.polarity for p in "ABC"}
        i0 = an.phasor("I0", i) * ti.polarity
        try:
            vl, il, _ = loop_quantities(vph, iph, i0, k0, fault)
        except ValueError:
            continue
        vphp = {p: an.ref.get("V" + p, 0j) for p in "ABC"}
        iphp = {p: an.ref.get("I" + p, 0j) * ti.polarity for p in "ABC"}
        i0p = an.ref.get("I0", 0j) * ti.polarity
        try:
            _, ilp, _ = loop_quantities(vphp, iphp, i0p, k0, fault)
        except ValueError:
            ilp = 0j

        r1 = e1_reactance(vl, il, z1)
        if r1.ok:
            m1.append(r1.m)
            d1 = r1.diagnostics
        r2 = e2_takagi(vl, il, il - ilp, z1)
        if r2.ok:
            m2.append(r2.m)
        if fault in SLG:
            r3 = e3_modified_takagi(vl, il, i0, z1, z0, ti.zs0, zs0_far,
                                    m_seed=float(np.median(m1)) if m1 else 0.5)
            if r3.ok:
                m3.append(r3.m)

    out: List[Estimate] = []
    for name, vals in (("E1", m1), ("E2", m2), ("E3", m3)):
        if not vals:
            reason = ("gated: single-phase-to-ground only" if name == "E3"
                      else "no valid sample in window")
            out.append(Estimate(method=name, m=float("nan"), residual=float("inf"),
                                ok=False, reason=reason, ends="single"))
            continue
        a = np.asarray(vals, dtype=float)
        med = float(np.median(a))
        spread = float(np.percentile(a, 95) - np.percentile(a, 5)) if a.size > 2 else float(
            a.max() - a.min()
        )
        diag = {"window_spread": spread, "n_samples": float(a.size), "terminal": ti.end}
        if name == "E1":
            diag.update(d1)
        out.append(Estimate(method=name, m=med, residual=spread, ends="single",
                            diagnostics=diag,
                            spread=(float(np.min(a)), float(np.max(a)))))
    return out


def _two_ended(
    s: TerminalInput, r: TerminalInput, line: Line, fault: str,
    span_s: Optional[Tuple[float, float]] = None,
    span_r: Optional[Tuple[float, float]] = None,
    n_pairs: int = 24,
) -> List[Estimate]:
    """E4 and E5 from paired window samples.

    The two windows are given in each record's own local time, already
    intersected on the inception instant by the caller. Record-local time is
    NOT comparable between terminals -- the relays capture different pre-fault
    lengths and their clocks are free-running -- so any overlap computed in
    raw local time is meaningless.

    During the settled fault the phasors are constant, so samples are paired
    by relative position within each terminal's own window. That works across
    different sample rates and window lengths and needs no common time grid.
    """
    zi_s = (s.analysed.ps.window_indices(*span_s) if span_s else s.analysed.indices())
    zi_r = (r.analysed.ps.window_indices(*span_r) if span_r else r.analysed.indices())
    if zi_s.size == 0 or zi_r.size == 0:
        why = "no usable window at " + ("S" if zi_s.size == 0 else "R")
        return [Estimate(method=m, m=float("nan"), residual=float("inf"), ok=False,
                         reason=why, ends="two") for m in ("E4", "E5")]

    n = min(n_pairs, zi_s.size, zi_r.size)
    ps = zi_s[np.linspace(0, zi_s.size - 1, n).round().astype(int)]
    pr = zi_r[np.linspace(0, zi_r.size - 1, n).round().astype(int)]

    three_phase = fault in ("ABC", "ABCG")
    if three_phase:
        v2s = [s.analysed.superimposed("V1", i) for i in ps]
        i2s = [s.analysed.superimposed("I1", i) * s.polarity for i in ps]
        v2r = [r.analysed.superimposed("V1", i) for i in pr]
        i2r = [r.analysed.superimposed("I1", i) * r.polarity for i in pr]
        note = "superimposed positive sequence (no negative sequence in a 3-ph fault)"
    else:
        v2s = [s.analysed.phasor("V2", i) for i in ps]
        i2s = [s.analysed.phasor("I2", i) * s.polarity for i in ps]
        v2r = [r.analysed.phasor("V2", i) for i in pr]
        i2r = [r.analysed.phasor("I2", i) * r.polarity for i in pr]
        note = "negative sequence"

    z1 = line.z1
    out: List[Estimate] = []

    if s.clock_good and r.clock_good:
        ms, resid = [], []
        for k in range(n):
            e = e4_synchronised(v2s[k], i2s[k], v2r[k], i2r[k], z1)
            if e.ok:
                ms.append(e.m)
                resid.append(e.residual)
        if ms:
            out.append(Estimate(method="E4", m=float(np.median(ms)),
                                residual=float(np.median(resid)), ends="two",
                                reason=note,
                                diagnostics={"m_imag_median": float(np.median(resid)),
                                             "n_samples": float(len(ms))}))
        else:
            out.append(Estimate(method="E4", m=float("nan"), residual=float("inf"),
                                ok=False, reason="no negative sequence", ends="two"))
    else:
        out.append(Estimate(method="E4", m=float("nan"), residual=float("inf"), ok=False,
                            reason="gated: clock quality not established at both ends",
                            ends="two"))

    e5 = e5_unsynchronised(v2s, i2s, v2r, i2r, z1)
    if e5.ok:
        e5.reason = note + "; " + (e5.reason or "")
    out.append(e5)
    return out


def _weigh(estimates: List[Estimate], terms: Dict[str, TerminalInput]) -> None:
    """Attach a weight to each estimate: prior x gate / (1 + normalised residual^2)."""
    for e in estimates:
        if not e.ok or not math.isfinite(e.m):
            e.diagnostics["weight"] = 0.0
            continue
        sigma = PRIOR_SIGMA.get(e.method, 0.03)
        w = 1.0 / (sigma * sigma)

        term = e.diagnostics.get("terminal")
        if term and term in terms and terms[term].sat:
            w *= 0.1                       # saturated CT: down-weight an order
            e.reason = (e.reason + "; " if e.reason else "") + "CT saturation at " + str(term)
        if e.ends == "two" and any(t.sat for t in terms.values()):
            w *= 0.3

        resid = e.residual if math.isfinite(e.residual) else 1.0
        scale = 0.02 if e.ends == "two" else 0.05
        w /= 1.0 + (resid / scale) ** 2

        if not (-0.05 <= e.m <= 1.05):
            w *= 0.02
            e.reason = (e.reason + "; " if e.reason else "") + "m outside the line"
        e.diagnostics["weight"] = float(w)


def locate(
    line: Line,
    terminals: Dict[str, TerminalInput],
    tower_band_pu: float = 0.0,
) -> LocationResult:
    """Run every applicable estimator and reconcile. 1 or 2 terminals."""
    if not terminals:
        return LocationResult(m=float("nan"), km_from_S=float("nan"),
                              km_from_R=float("nan"), interval_pu=(float("nan"),) * 2,
                              interval_km=(float("nan"),) * 2, method="none",
                              mode="none", fault_type="NONE",
                              caveats=["no records"])

    terms = list(terminals.values())
    fault, caveats, cross_country = _fault_consensus(terms)

    estimates: List[Estimate] = []
    for end, ti in sorted(terminals.items()):
        for e in _single_ended(ti, line, fault):
            if e.ok and end == "R":
                e.m = 1.0 - e.m          # R measures from R; report from S
            e.method = e.method + "@" + end
            e.diagnostics["terminal"] = end
            estimates.append(e)

    two = "S" in terminals and "R" in terminals and not cross_country
    if two:
        s, r = terminals["S"], terminals["R"]
        # Align the two windows on the fault inception, which is the same
        # physical instant at both ends to within the travel time (well under
        # one sample). Record-local time is not comparable between terminals.
        inc_s = float(s.analysed.notes.get("inception_t", 0.0))
        inc_r = float(r.analysed.notes.get("inception_t", 0.0))
        shift = inc_s - inc_r
        ov = overlap_window(s.analysed.window, r.analysed.window,
                            s.analysed.freq, shift_b=shift)
        if ov.cycles < 0.5:
            caveats.append("two-ended overlap only " + format(ov.cycles, ".2f")
                           + " cycles - falling back to single-ended")
            two = False
        else:
            if ov.cycles < 1.0:
                caveats.append("two-ended overlap " + format(ov.cycles, ".2f")
                               + " cycles - reduced accuracy")
            span_s = (ov.t_start, ov.t_end)
            span_r = (ov.t_start - shift, ov.t_end - shift)
            estimates.extend(_two_ended(s, r, line, fault, span_s, span_r))
    elif cross_country:
        pass
    elif len(terminals) == 1:
        caveats.append("SINGLE-ENDED: far-end record not available; accuracy is "
                       "3-15 % of line length, not 0.1-1 %")

    if line.series_compensated:
        caveats.append("line is series compensated - impedance-based location "
                       "is not valid across the capacitor; result suppressed")
        for e in estimates:
            e.ok = False
            e.reason = "series compensated line"

    _weigh(estimates, terminals)

    usable = [e for e in estimates if e.ok and e.diagnostics.get("weight", 0.0) > 0]
    if not usable:
        return LocationResult(m=float("nan"), km_from_S=float("nan"),
                              km_from_R=float("nan"), interval_pu=(float("nan"),) * 2,
                              interval_km=(float("nan"),) * 2, method="none",
                              mode="none", fault_type=fault, estimates=estimates,
                              caveats=caveats + ["no estimator produced a usable answer"])

    # A healthy two-ended estimate is not averaged with single-ended ones.
    # Blending a 3 %-class method into a 0.03 %-class method can only degrade
    # it. The single-ended results stay in the table, and their disagreement
    # with the two-ended answer is itself a diagnostic (rule MS-03 class), but
    # they do not move the number.
    two_ok = [e for e in usable if e.ends == "two" and e.residual < 0.05]
    blend = two_ok if two_ok else usable
    ws = np.asarray([e.diagnostics["weight"] for e in blend])
    msv_blend = np.asarray([e.m for e in blend])
    msv = np.asarray([e.m for e in usable])
    m = float(np.sum(ws * msv_blend) / np.sum(ws))
    best = max(blend, key=lambda e: e.diagnostics["weight"])
    mode = "two-ended" if best.ends == "two" else "single-ended"

    # interval: the winning estimator's own window spread, widened by the
    # disagreement between methods, which is itself diagnostic
    win = best.spread or (best.m, best.m)
    disagree = float(np.max(msv) - np.min(msv)) if msv.size > 1 else 0.0
    blend_spread = (float(np.max(msv_blend) - np.min(msv_blend))
                    if msv_blend.size > 1 else 0.0)
    if two_ok:
        # interval from the two-ended window spread; the single-ended methods
        # disagreeing by 3 % is expected and must not inflate the interval
        half = max(abs(win[1] - win[0]) / 2.0, blend_spread / 2.0, 0.001)
    else:
        half = max(abs(win[1] - win[0]) / 2.0, disagree / 2.0, 0.002)
    lo, hi = m - half, m + half

    km = line.m_to_km(min(max(m, 0.0), 1.0))
    klo = line.m_to_km(min(max(lo, 0.0), 1.0))
    khi = line.m_to_km(min(max(hi, 0.0), 1.0))
    band = max(abs(khi - klo) / 2.0, tower_band_pu * line.length_km)
    towers = line.towers_near(km, max(band, 0.5))

    res = LocationResult(
        m=m, km_from_S=km, km_from_R=line.length_km - km,
        interval_pu=(lo, hi), interval_km=(klo, khi),
        method=best.method, mode=mode, fault_type=fault, estimates=estimates,
        towers=towers, likely_tower=line.nearest_tower(km), caveats=caveats,
        diagnostics={
            "method_disagreement_pu": disagree,
            "n_estimators": float(len(usable)),
            "_km_fn": lambda x: line.m_to_km(min(max(x, 0.0), 1.0)),
        },
    )
    return res
