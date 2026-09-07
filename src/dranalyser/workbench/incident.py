"""Turn an assigned bundle into ONE incident report.

This is the same pipeline `dranalyse report` runs; the difference is that its
input is a bundle with the operator's declaration attached, so it can carry
records the estimators do not use -- a second relay at the same terminal, a
blocked record, a duplicate -- and still say what became of each of them.
PROJECT_CONTEXT.md §2.4: one fault, one report, many records.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..comtrade.conformance import check
from ..comtrade.parser import read_cff, read_comtrade
from ..dsp.pipeline import analyse
from ..faultloc.ensemble import TerminalInput, locate
from ..registry.loader import load_line
from ..registry.rio import read_rio
from ..report import build, render, write
from ..rules.engine import apply_rules, load_rules
from ..rules.features import incident_features
from .bundle import Bundle, BundleFile
from .corroborate import Disagreement, Measure, corroborate, measure


@dataclass
class IncidentResult:
    """What the analysis made of one bundle, and what it declined to use."""

    incident_id: str = ""
    verdict: str = ""
    report_path: str = ""
    location_text: str = "not computed - no line definition supplied"
    used: Dict[str, str] = field(default_factory=dict)      # end -> file name
    excluded: List[str] = field(default_factory=list)       # human-readable
    errors: List[str] = field(default_factory=list)
    # Every usable record at each end, primary first, reduced to comparable
    # quantities -- and what the comparison found.
    measures: Dict[str, List[Measure]] = field(default_factory=dict)
    disagreements: List[Disagreement] = field(default_factory=list)


def _read(bundle: Bundle, bf: BundleFile, end: str):
    full = os.path.join(bundle.root, bf.name.replace("/", os.sep))
    rec = (read_cff(full, terminal_end=end) if full.lower().endswith(".cff")
           else read_comtrade(full, terminal_end=end))
    return rec


def _why_excluded(f: BundleFile) -> str:
    if f.kind == "settings":
        return ""
    if f.duplicate_of:
        return f.name + " -- byte-identical to " + f.duplicate_of
    if not f.ok:
        return f.name + " -- " + (f.error or "did not parse")
    if f.blocked:
        blocks = [x for x in f.flags if x.startswith("[BLOCK")]
        return f.name + " -- blocked by the conformance gate: " + \
            (blocks[0] if blocks else "see flags")
    if not f.terminal_end:
        return f.name + " -- no terminal declared by the operator"
    if f.role != "primary":
        return f.name + " -- attached at end " + f.terminal_end + \
            " as corroboration; it does not drive the estimate"
    return ""


def analyse_bundle(bundle: Bundle, line_path: str = "", out_dir: str = "",
                   confirm_url: str = "") -> IncidentResult:
    """Analyse the primary record at each declared end and report once."""
    res = IncidentResult()
    line = None
    if line_path:
        try:
            line = load_line(line_path)
        except Exception as exc:                # noqa: BLE001 - shown, not raised
            res.errors.append("line definition not loaded: " + str(exc)[:200])

    ans: Dict[str, Any] = {}
    settings: Dict[str, Any] = {}
    for end in ("S", "R"):
        # by_end() puts the primary first. Every record at the end is
        # analysed: the primary drives the estimators, the rest corroborate.
        # A second relay in the bay is free evidence and refusing to look at
        # it is how a wiring fault stays invisible.
        for pos, f in enumerate(bundle.by_end(end)):
            try:
                rec = _read(bundle, f, end)
                check(rec, nominal_kv=line.kv if line else None)
                if rec.blocked():
                    res.excluded.append(f.name
                                        + " -- blocked by the conformance gate")
                    continue
                term = line.terminals[end] if line else None
                an = analyse(rec, vt_type=term.it.vt_type if term else "CVT")
                res.measures.setdefault(end, []).append(measure(an, f.name))
                if pos == 0:
                    ans[end] = an
                    res.used[end] = f.name
            except Exception as exc:            # noqa: BLE001
                res.errors.append(f.name + ": " + type(exc).__name__ + " "
                                  + str(exc)[:200])
    res.disagreements = corroborate(res.measures)

    for sf in bundle.settings():
        if not sf.name.lower().endswith(".rio"):
            continue
        try:
            settings["S" if "S" in res.used else "R"] = read_rio(
                os.path.join(bundle.root, sf.name.replace("/", os.sep)))
        except Exception as exc:                # noqa: BLE001
            res.errors.append(sf.name + ": " + str(exc)[:200])

    for f in bundle.files:
        why = _why_excluded(f)
        if why and f.name not in res.used.values():
            res.excluded.append(why)

    if not ans:
        res.verdict = "No record reached the analysis."
        return res

    loc = None
    if line is not None:
        loc = locate(line, {e: TerminalInput(analysed=a, end=e,
                                             zs1=line.terminals[e].zs1,
                                             zs0=line.terminals[e].zs0,
                                             polarity=line.terminals[e].i_polarity)
                            for e, a in ans.items()})
    z2 = 0.35
    for s in settings.values():
        if s.zone("Z2"):
            z2 = s.zone("Z2").t1
    feats = incident_features(ans, location=loc, line=line, settings=settings,
                              z2_time_s=z2)
    rr = apply_rules(feats, load_rules())
    rep = build(ans, feats, rr, location=loc, line=line, settings=settings,
                ground_truth_url=confirm_url)
    render(rep)

    out = out_dir or bundle.root
    os.makedirs(out, exist_ok=True)
    res.report_path = write(rep, os.path.join(out, rep.incident_id + ".html"))
    res.incident_id = rep.incident_id
    res.verdict = rr.verdict
    if loc is not None and loc.ok:
        res.location_text = (format(loc.km_from_S, ".3f") + " km from "
                             + line.terminals["S"].substation
                             + " by " + loc.method + " (" + loc.mode + ")")
    elif line is None:
        res.location_text = ("not computed - no line definition supplied, so "
                             "there are no line constants to locate against")
    else:
        why = "; ".join(loc.caveats) if (loc and loc.caveats) else "no usable estimate"
        res.location_text = "refused - " + why
    return res


def default_line_files(registry_dir: str = "data/registry") -> List[str]:
    """Line definitions the operator can pick from in the form."""
    if not os.path.isdir(registry_dir):
        return []
    return sorted(os.path.join(registry_dir, n) for n in os.listdir(registry_dir)
                  if n.lower().endswith((".yaml", ".yml")))
