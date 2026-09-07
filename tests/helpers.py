"""Shared fixtures for the test suite."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dranalyser.comtrade.conformance import check
from dranalyser.comtrade.parser import read_comtrade
from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc.ensemble import TerminalInput, locate
from dranalyser.registry.loader import load_line
from dranalyser.registry.model import uniform_line
from dranalyser.registry.rio import read_rio
from dranalyser.rules.features import incident_features
from dranalyser.synth.generator import SynthSpec, TerminalSpec, generate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINE_YAML = os.path.join(ROOT, "data", "registry", "dhn-nnr.yaml")


def synthetic_incident(m: float = 0.42, fault: str = "AG",
                       rf: float = 5.0, two_ended: bool = True) -> Dict[str, Any]:
    """A complete two-ended feature set, for exercising every rule condition."""
    spec = SynthSpec(
        m=m, fault=fault, rf=rf,
        S=TerminalSpec(fs=1000.0, prefault_s=0.12, post_s=0.25, breaker_time_s=0.060),
        R=TerminalSpec(fs=1200.0, prefault_s=0.16, post_s=0.25, breaker_time_s=0.060,
                       sample_phase=0.37, clock_offset_s=1418.0),
    )
    case = generate(spec)
    line = uniform_line("T", "test", spec.kv, spec.line_km, spec.z1_per_km,
                        spec.z0_per_km, spec.zs1_S, spec.zs0_S, spec.zs1_R, spec.zs0_R)
    ends = ("S", "R") if two_ended else ("S",)
    ans = {e: analyse(case.records[e]) for e in ends}
    terms = {e: TerminalInput(analysed=ans[e], end=e,
                              zs1=spec.zs1_S if e == "S" else spec.zs1_R,
                              zs0=spec.zs0_S if e == "S" else spec.zs0_R)
             for e in ends}
    res = locate(line, terms)
    return incident_features(ans, location=res, line=line)


def real_incident(cfg_path: str, rio_path: Optional[str] = None) -> Dict[str, Any]:
    """Feature set for one real record, treated as end S."""
    line = load_line(LINE_YAML)
    if rio_path is None:
        cand = os.path.join(os.path.dirname(cfg_path), "DR-1.rio")
        rio_path = cand if os.path.exists(cand) else None
    rio = read_rio(rio_path) if rio_path else None
    rec = read_comtrade(cfg_path, terminal_end="S")
    check(rec, nominal_kv=line.kv)
    an = analyse(rec, vt_type=line.terminals["S"].it.vt_type)
    res = locate(line, {"S": TerminalInput(analysed=an, end="S",
                                           zs1=line.terminals["S"].zs1,
                                           zs0=line.terminals["S"].zs0)})
    return incident_features({"S": an}, location=res, line=line,
                             settings={"S": rio} if rio else None, z2_time_s=0.45)
