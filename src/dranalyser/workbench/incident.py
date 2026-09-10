"""Turn an assigned bundle into ONE incident report.

This is the same pipeline `dranalyse report` runs; the difference is that its
input is a bundle with the operator's declaration attached, so it can carry
records the estimators do not use -- a second relay at the same terminal, a
blocked record, a duplicate -- and still say what became of each of them.
PROJECT_CONTEXT.md §2.4: one fault, one report, many records.
"""
from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..comtrade.conformance import check
from ..comtrade.parser import read_cff, read_comtrade
from ..dsp.pipeline import analyse
from ..dsp.correlation import onset_profile
from ..faultloc.ensemble import TerminalInput, locate
from ..registry.loader import load_line
from ..report import build, render, write
from ..report.navigation import navigation_record
from ..rules.engine import apply_rules, load_rules
from ..rules.features import incident_features
from ..rules.evidence import relay_evidence, terminal_evidence
from ..rules.operation_compare import compare_operations
from .bundle import Bundle, BundleFile
from .corroborate import Disagreement, Measure, corroborate, measure
from .settings import settings_by_record
from .stage_review import apply_stage_review
from .stage_location import stage_locations
from .audits import audit_bundle
from ..standards.checklist import reference_pack


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
    relay_evidence: List[dict] = field(default_factory=list)
    terminal_evidence: List[dict] = field(default_factory=list)
    operation_comparisons: List[dict] = field(default_factory=list)
    standards_audits: List[dict] = field(default_factory=list)
    standards_sources: List[dict] = field(default_factory=list)
    navigator_path: str = ""
    stage_locations: List[dict] = field(default_factory=list)


def _read(bundle: Bundle, bf: BundleFile, end: str):
    full = os.path.join(bundle.root, bf.name.replace("/", os.sep))
    rec = (read_cff(full, terminal_end=end, channel_mapping=bf.channel_mapping) if full.lower().endswith(".cff")
           else read_comtrade(full, terminal_end=end, channel_mapping=bf.channel_mapping))
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
    profiles = {}
    records = {}
    navigation = []
    settings: Dict[str, Any] = {}
    by_record, bindings, settings_errors = settings_by_record(bundle, [f.name for f in bundle.records()])
    for end in ("S", "R"):
        # by_end() puts the primary first. Every record at the end is
        # analysed: the primary drives the estimators, the rest corroborate.
        # A second relay in the bay is free evidence and refusing to look at
        # it is how a wiring fault stays invisible.
        for pos, f in enumerate(bundle.by_end(end)):
            try:
                rec = _read(bundle, f, end)
                records[f.name] = rec
                check(rec, nominal_kv=line.kv if line else None)
                if rec.blocked():
                    res.excluded.append(f.name
                                        + " -- blocked by the conformance gate")
                    continue
                term = line.terminals[end] if line else None
                an = analyse(rec, vt_type=term.it.vt_type if term else "CVT")
                res.measures.setdefault(end, []).append(measure(an, f.name))
                res.relay_evidence.append(relay_evidence(an, f.name, end, f.role, f.relay_id,
                                                        getattr(f, "protection_system", "unknown")))
                res.relay_evidence[-1]['mapping_original_flags'] = f.mapping_original_flags
                apply_stage_review(res.relay_evidence[-1], f.stage_review, bundle.line_id, bundle.bundle_id)
                profiles[f.name] = onset_profile(an)
                try:
                    nav = navigation_record(an, res.relay_evidence[-1], by_record.get(f.name), bindings[f.name], f.rx_review)
                    navigation.append(nav)
                    res.relay_evidence[-1]['rx_context'] = nav.get('rx', {}).get('context')
                except Exception as exc:
                    navigation.append({'file': f.name, 'status': 'unavailable', 'reason': str(exc)[:200]})
                if pos == 0:
                    ans[end] = an
                    res.used[end] = f.name
            except Exception as exc:            # noqa: BLE001
                res.errors.append(f.name + ": " + type(exc).__name__ + " "
                                  + str(exc)[:200])
    res.disagreements = corroborate(res.measures)
    analysed_files = {r["file"] for r in res.relay_evidence}
    for f in bundle.records():
        if f.name not in analysed_files:
            res.relay_evidence.append({"file": f.name, "end": f.terminal_end, "role": f.role,
                                      "device_id": f.device_id, "relay_id": f.relay_id or "unknown",
                                      "protection_system": getattr(f, "protection_system", "unknown"),
                                      'channel_mapping': f.channel_mapping, 'channel_inventory': f.channel_inventory,
                                      'mapping_original_flags': f.mapping_original_flags,
                                      "status": "unavailable", "reason":
                                      next((e for e in res.errors + res.excluded if e.startswith(
                                          (f.name + ":", f.name + " --"))), _why_excluded(f) or "not analysed")})
    res.terminal_evidence = terminal_evidence(res.relay_evidence)
    res.operation_comparisons = compare_operations(res.relay_evidence, profiles)
    res.stage_locations = stage_locations(line, ans, res.relay_evidence, res.used)

    settings = {end: by_record[name] for end, name in res.used.items() if name in by_record}
    res.errors.extend(settings_errors)
    res.standards_audits = audit_bundle(bundle, records, by_record, bindings)
    res.standards_sources = reference_pack()
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        res.navigator_path = os.path.join(out_dir, 'navigator.json')
        with open(res.navigator_path, 'w', encoding='utf-8') as stream:
            json.dump({'version': 1, 'records': navigation}, stream, allow_nan=False)

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
    rep.relay_evidence = res.relay_evidence
    rep.comparisons = [d.text for d in res.disagreements]
    rep.operation_comparisons = res.operation_comparisons
    rep.stage_locations = res.stage_locations
    rep.standards_audits, rep.standards_sources = res.standards_audits, res.standards_sources
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
