"""Builds the two-page incident report.

Page 1 is a decision, readable in ninety seconds by a shift engineer.
Page 2 is the evidence for it. Everything else belongs in the interactive
event view, not here: the two-page discipline is what stops the report
becoming a wall of waveforms nobody reads.

The output is one self-contained HTML file with inline SVG. No web fonts, no
CDN, no plotting library, so it renders on an isolated network and converts
to PDF with WeasyPrint where one is installed.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..dsp.pipeline import Analysed
from ..faultloc.ensemble import LocationResult
from ..registry.model import Line
from ..registry.rio import RioSettings
from ..rules.engine import RuleResult
from ..rules.signals import map_signals
from . import graphics as g

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")

VERDICT_CLASS = {
    "Correct operation": "ok",
    "Correct but investigate": "warn",
    "Incorrect operation": "bad",
}

# Signals worth a row on the digital timeline, in the order an engineer reads
# them: what started, what decided, what was sent, what opened, what reclosed.
TIMELINE_ORDER = (
    "START", "Z1", "Z2", "Z3", "TRIP", "TRIP_A", "TRIP_B", "TRIP_C", "TRIP_3P",
    "TRIP_Z2", "TRIP_Z3", "CARRIER_SEND", "CARRIER_RECV", "CARRIER_FAIL",
    "OC_PICKUP", "OC_TRIP", "EF_PICKUP", "EF_TRIP",
    "CB_OPEN_A", "CB_OPEN_B", "CB_OPEN_C", "ANY_POLE_DEAD",
    "AR_IN_PROGRESS", "AR_CLOSE", "AR_LOCKOUT", "AR_BLOCK",
    "DEFINITIVE_TRIP", "LOCKOUT_86", "VT_FAIL", "POWER_SWING", "SOTF",
)


def _fmt(v: Any, spec: str = ".1f", dash: str = "-") -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return dash
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        return format(v, spec)
    return str(v)


def incident_id(line_id: str, when: Optional[_dt.datetime], salt: str = "") -> str:
    stamp = when.strftime("%Y%m%dT%H%M%S") if when else "unknown"
    h = hashlib.sha256((line_id + stamp + salt).encode()).hexdigest()[:6]
    return line_id + "-" + stamp + "-" + h


# --------------------------------------------------------------------------
def _spans(rec, channels: Sequence[str], t0: float) -> List[Tuple[float, float]]:
    """Assert/deassert intervals in ms from inception, over all channels."""
    out: List[Tuple[float, float]] = []
    for ch in channels:
        d = rec.digital.get(ch)
        if d is None:
            continue
        arr = np.asarray(d, dtype=int)
        on = None
        for i in range(1, arr.size):
            if arr[i] and not arr[i - 1]:
                on = float(rec.t[i])
            elif on is not None and arr[i - 1] and not arr[i]:
                out.append(((on - t0) * 1000.0, (float(rec.t[i]) - t0) * 1000.0))
                on = None
        if on is not None:
            out.append(((on - t0) * 1000.0, (float(rec.t[-1]) - t0) * 1000.0))
    return out


def _trajectory(an: Analysed, settings: Optional[RioSettings], ct: float, vt: float,
                fault: str) -> List[complex]:
    """Apparent loop impedance per sample, in secondary ohm."""
    if settings is None:
        return []
    from ..faultloc.estimators import loop_quantities

    k0 = settings.k0() or 0j
    sec = 1.0 / settings.secondary_to_primary(ct, vt)
    out: List[complex] = []
    t0 = float(an.notes.get("inception_t", 0.0))
    lo = int(np.searchsorted(an.ps.t, t0))
    hi = min(an.ps.t.size, lo + int(6 * an.ps.fs / an.freq))
    for i in range(max(lo, an.ps.valid_from), hi):
        vph = {p: an.phasor("V" + p, i) for p in "ABC"}
        iph = {p: an.phasor("I" + p, i) for p in "ABC"}
        try:
            vl, il, _ = loop_quantities(vph, iph, an.phasor("I0", i), k0, fault)
        except (ValueError, KeyError):
            return []
        if abs(il) < 1e-9:
            continue
        z = (vl / il) * sec
        if math.isfinite(z.real) and math.isfinite(z.imag):
            out.append(z)
    return out


def _zone_polygons(settings: Optional[RioSettings], ground: bool) -> List[Dict[str, object]]:
    if settings is None:
        return []
    out = []
    for z in settings.zones:
        c = z.characteristic(ground)
        if c and len(c.vertices) >= 3:
            out.append({"name": z.name, "vertices": c.vertices})
    return out


@dataclass
class IncidentReport:
    incident_id: str
    line: Optional[Line]
    features: Dict[str, Any]
    rules: RuleResult
    location: Optional[LocationResult]
    analysed: Dict[str, Analysed]
    settings: Dict[str, RioSettings] = field(default_factory=dict)
    ground_truth_url: str = ""
    generated_at: str = ""
    html: str = ""


def build(
    analysed: Dict[str, Analysed],
    features: Dict[str, Any],
    rules: RuleResult,
    location: Optional[LocationResult] = None,
    line: Optional[Line] = None,
    settings: Optional[Dict[str, RioSettings]] = None,
    ground_truth_url: str = "",
) -> IncidentReport:
    settings = settings or {}
    first = analysed[sorted(analysed)[0]]
    when = first.record.trigger_time
    lid = line.id if line else (first.record.station or "LINE")
    rid = incident_id(lid, when, first.record.content_hash[:8])
    url = ground_truth_url or ("http://dr/confirm/" + rid)
    return IncidentReport(
        incident_id=rid, line=line, features=features, rules=rules,
        location=location, analysed=analysed, settings=settings,
        ground_truth_url=url,
        generated_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def render(rep: IncidentReport) -> str:
    from jinja2 import Template

    f, ends = rep.features, sorted(rep.analysed)
    line = rep.line
    ground = bool(f.get("is_ground_fault"))

    panels, rows = [], []
    tmin, tmax = -40.0, 140.0
    for end in ends:
        an = rep.analysed[end]
        rec = an.record
        t0 = float(an.notes.get("inception_t", 0.0))
        t_ms = (rec.t - t0) * 1000.0
        clear = f.get(end + "_clear_ms")
        hi = max(140.0, (clear or 0) + 60.0)
        sel = (t_ms >= -40.0) & (t_ms <= hi)
        tmax = max(tmax, hi)
        ev = []
        for key, label in ((end + "_trip_ms", "trip"), (end + "_open_ms", "open"),
                           (end + "_carrier_recv_ms", "carrier rx")):
            if isinstance(f.get(key), float):
                ev.append((f[key], label))
        sub = line.terminals[end].substation if line else end
        panels.append({"title": "End " + end + " - " + sub + " - currents",
                       "t_ms": t_ms[sel], "unit": "A primary",
                       "traces": {p: rec.analog["I" + p][sel] for p in "ABC"
                                  if "I" + p in rec.analog},
                       "events": ev})
        panels.append({"title": "End " + end + " - " + sub + " - voltages",
                       "t_ms": t_ms[sel], "unit": "kV primary",
                       "traces": {p: rec.analog["V" + p][sel] / 1000.0 for p in "ABC"
                                  if "V" + p in rec.analog},
                       "events": ev})
        sm = map_signals(list(rec.digital))
        for sig in TIMELINE_ORDER:
            chans = sm.channels(sig)
            if not chans:
                continue
            sp = _spans(rec, chans, t0)
            if sp:
                rows.append((end, sig, sp))

    s_end = ends[0]
    an0 = rep.analysed[s_end]
    st = rep.settings.get(s_end)
    ct = line.terminals[s_end].it.ct_ratio if line else 1.0
    vt = line.terminals[s_end].it.vt_ratio if line else 1.0
    traj = _trajectory(an0, st, ct, vt, an0.fault_type)
    reach = []
    if st is not None:
        for z in st.forward_zones:
            c = z.characteristic(ground)
            if c:
                reach.append((z.name, c.reach_at_angle(st.line_angle_deg)))

    idx = an0.indices()
    ph = {}
    if idx.size:
        i = int(idx[idx.size // 2])
        ph = {"V1": an0.phasor("V1", i), "V2": an0.phasor("V2", i),
              "V0": an0.phasor("V0", i), "I1": an0.phasor("I1", i),
              "I2": an0.phasor("I2", i), "I0": an0.phasor("I0", i)}

    svg = {
        "oscillogram": g.oscillogram(panels),
        "timeline": g.digital_timeline(rows, tmin, tmax),
        "rx": g.rx_diagram(_zone_polygons(st, ground), traj,
                           st.line_angle_deg if st else 80.0, reach),
        "phasors": g.phasor_diagram(ph, "Sequence phasors, end " + s_end),
        "qr": g.qr_svg(rep.ground_truth_url),
    }

    caveats: List[str] = []
    for end in ends:
        for fl in rep.analysed[end].record.flags:
            if fl.severity in ("block", "flag"):
                caveats.append("End " + end + ": " + fl.message)
    if rep.location is not None:
        caveats.extend(rep.location.caveats)

    with open(TEMPLATE, "r", encoding="utf-8") as fh:
        tpl = Template(fh.read())
    rep.html = tpl.render(
        r=rep, f=f, line=line, ends=ends, svg=svg, caveats=caveats,
        verdict=rep.rules.verdict, vclass=VERDICT_CLASS.get(rep.rules.verdict, "warn"),
        findings=rep.rules.top(3), all_findings=rep.rules.findings,
        skipped=rep.rules.skipped, loc=rep.location, fmt=_fmt,
        settings=rep.settings, sub=lambda e: (line.terminals[e].substation
                                              if line else e),
    )
    return rep.html


def write(rep: IncidentReport, path: str) -> str:
    html = rep.html or render(rep)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path
