"""Load a line definition from YAML into the registry model.

The registry is where correctness lives. Anything the analyser needs about
the physical line comes from here, so that a wrong answer can always be
traced to a stated number rather than to a constant buried in code.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import yaml

from .model import (InstrumentTransformer, Line, LineSection, Relay,
                    RelaySetting, Terminal, Tower)


def _cx(v: Any, default: complex = 0j) -> complex:
    """Accept [r, x], {r:, x:}, "r+xj" or a bare number."""
    if v is None:
        return default
    if isinstance(v, complex):
        return v
    if isinstance(v, (int, float)):
        return complex(float(v), 0.0)
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return complex(float(v[0]), float(v[1]))
    if isinstance(v, dict):
        return complex(float(v.get("r", 0.0)), float(v.get("x", 0.0)))
    return complex(str(v).replace(" ", ""))


def _terminal(end: str, d: Dict[str, Any]) -> Terminal:
    d = d or {}
    it = InstrumentTransformer(
        ct_ratio=float(d.get("ct_ratio", 1.0)),
        vt_ratio=float(d.get("vt_ratio", 1.0)),
        vt_type=str(d.get("vt_type", "CVT")).upper(),
        vt_location=str(d.get("vt_location", "line")).lower(),
        ct_knee_v=d.get("ct_knee_v"),
        ct_class=str(d.get("ct_class", "")),
    )
    relays: List[Relay] = []
    for r in d.get("relays", []) or []:
        settings = []
        for s in r.get("settings", []) or []:
            settings.append(RelaySetting(
                effective_from=str(s.get("effective_from", "")),
                effective_to=str(s.get("effective_to", "")),
                scheme=str(s.get("scheme", "PUTT")),
                z1_reach_pu=float(s.get("z1_reach_pu", 0.8)),
                z2_reach_pu=float(s.get("z2_reach_pu", 1.2)),
                z3_reach_pu=float(s.get("z3_reach_pu", 2.0)),
                z2_time_s=float(s.get("z2_time_s", 0.35)),
                z3_time_s=float(s.get("z3_time_s", 0.8)),
                line_angle_deg=float(s.get("line_angle_deg", 80.0)),
                k0_convention=str(s.get("k0_convention", "complex_k0")),
                k0_params={k: float(v) for k, v in (s.get("k0_params", {}) or {}).items()},
            ))
        relays.append(Relay(
            id=str(r.get("id", "")), make=str(r.get("make", "")),
            model=str(r.get("model", "")), function=str(r.get("function", "main1")),
            retrieval=str(r.get("retrieval", "iec61850")), settings=settings,
        ))
    return Terminal(
        end=end, substation=str(d.get("substation", end)), it=it,
        zs1=_cx(d.get("zs1")), zs0=_cx(d.get("zs0")), relays=relays,
        i_polarity=int(d.get("i_polarity", 1)),
    )


def load_line(path: str) -> Line:
    with open(path, "r", encoding="utf-8") as fh:
        d = yaml.safe_load(fh) or {}
    return line_from_dict(d)


def line_from_dict(d: Dict[str, Any]) -> Line:
    secs: List[LineSection] = []
    for i, s in enumerate(d.get("sections", []) or []):
        secs.append(LineSection(
            seq=int(s.get("seq", i + 1)),
            from_km=float(s["from_km"]), to_km=float(s["to_km"]),
            r1=float(s["r1"]), x1=float(s["x1"]),
            r0=float(s["r0"]), x0=float(s["x0"]),
            b1=float(s.get("b1", 0.0)), b0=float(s.get("b0", 0.0)),
            conductor=str(s.get("conductor", "")),
        ))
    if not secs:
        raise ValueError("line definition has no sections; Z1 and Z0 per km are "
                         "mandatory - a wrong Z0 is the largest single cause of "
                         "a wrong location")

    terms = {e: _terminal(e, (d.get("terminals", {}) or {}).get(e, {}))
             for e in ("S", "R")}

    towers: List[Tower] = []
    for t in d.get("towers", []) or []:
        towers.append(Tower(number=str(t["number"]), chainage_km=float(t["chainage_km"]),
                            lat=t.get("lat"), lon=t.get("lon")))
    span = d.get("tower_span_km")
    if not towers and span:
        total = secs[-1].to_km
        n = int(total / float(span)) + 1
        towers = [Tower(number=str(i + 1), chainage_km=i * float(span)) for i in range(n)]

    return Line(
        id=str(d.get("id", "LINE")), name=str(d.get("name", "")),
        kv=float(d.get("kv", 220.0)), sections=secs, terminals=terms,
        towers=towers, double_circuit=bool(d.get("double_circuit", False)),
        series_compensated=bool(d.get("series_compensated", False)),
    )


def dump_template(path: str, line_id: str = "EXAMPLE") -> None:
    """Write a commented starter file so a protection engineer can fill it in."""
    text = """# Line definition for the DR analyser registry.
# Z0 is the number most often wrong and it dominates single-ended accuracy.
# The two-ended method E5 does not use Z0 at all, which is why it is primary.
id: {lid}
name: Example 220 kV line
kv: 220
double_circuit: false
series_compensated: false     # true suppresses impedance-based location

# One entry per homogeneous stretch. m is per unit of REACTANCE, so a mixed
# conductor line must be described section by section or the km conversion
# will be wrong.
sections:
  - seq: 1
    from_km: 0.0
    to_km: 100.0
    r1: 0.030      # ohm/km positive sequence
    x1: 0.400
    r0: 0.250      # ohm/km zero sequence
    x0: 1.200
    conductor: ACSR ZEBRA

tower_span_km: 0.35           # used only if no explicit tower list is given
# towers:
#   - {{number: "118", chainage_km: 42.10}}

terminals:
  S:
    substation: DHONE
    ct_ratio: 800
    vt_ratio: 2000
    vt_type: CVT              # CVT gets 1.5 cycles of blanking; VT gets 0.25
    vt_location: line
    zs1: [1.0, 12.0]          # source impedance, primary ohm, [R, X]
    zs0: [2.0, 20.0]
    i_polarity: 1             # +1 = current positive from bus into the line
    relays:
      - id: DHONE-M2
        make: Siemens
        model: 7SA522
        function: main2
        retrieval: iec60870-5-103
        settings:
          - effective_from: "2024-01-01"
            scheme: PUTT
            z1_reach_pu: 0.80
            z2_reach_pu: 1.20
            z2_time_s: 0.35
            line_angle_deg: 81.0
            # Store the relay's NATIVE form. k0 is derived, never typed in:
            # a SIPROTEC holds two real ratios whose complex k0 has an angle
            # that is invisible if you copy XE/XL into a "k0 magnitude" box.
            k0_convention: siemens_re_xe
            k0_params: {{re_rl: 1.020, xe_xl: 0.800}}
  R:
    substation: NANDYAL
    ct_ratio: 800
    vt_ratio: 2000
    vt_type: CVT
    zs1: [1.5, 18.0]
    zs0: [3.0, 30.0]
""".format(lid=line_id)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
