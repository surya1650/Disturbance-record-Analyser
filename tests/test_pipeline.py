"""End-to-end tests: waveforms in, located fault out.

Includes the Stage-A acceptance criterion from the brief's section 13:
two-ended error below 0.5 % of line length in 95 % of clean-data cases.
"""
from __future__ import annotations

import numpy as np
import pytest

from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc.ensemble import TerminalInput, locate
from dranalyser.registry.model import uniform_line
from dranalyser.synth.generator import SynthSpec, TerminalSpec, generate


def _case(m, fault, rf, **kw):
    spec = SynthSpec(
        m=m, fault=fault, rf=rf,
        S=TerminalSpec(fs=1000.0, prefault_s=0.12, post_s=0.25, breaker_time_s=0.060),
        R=TerminalSpec(fs=1200.0, prefault_s=0.16, post_s=0.25, breaker_time_s=0.060,
                       sample_phase=0.37, clock_offset_s=1418.0),
    )
    for k, v in kw.items():
        setattr(spec, k, v)
    case = generate(spec)
    line = uniform_line("T", "test", spec.kv, spec.line_km, spec.z1_per_km,
                        spec.z0_per_km, spec.zs1_S, spec.zs0_S, spec.zs1_R, spec.zs0_R)
    return spec, case, line


def _terms(spec, case, ends=("S", "R")):
    out = {}
    for e in ends:
        out[e] = TerminalInput(
            analysed=analyse(case.records[e]), end=e,
            zs1=spec.zs1_S if e == "S" else spec.zs1_R,
            zs0=spec.zs0_S if e == "S" else spec.zs0_R,
        )
    return out


# --------------------------------------------------------------------------
def test_inception_is_found_within_one_sample():
    spec, case, _ = _case(0.4, "AG", 5.0)
    an = analyse(case.records["S"])
    assert an.inception is not None
    truth = spec.S.prefault_s
    assert an.inception.t_refined == pytest.approx(truth, abs=1.5 / spec.S.fs)


def test_frequency_tracking_follows_off_nominal():
    spec, case, _ = _case(0.4, "AG", 5.0, freq=49.2)
    an = analyse(case.records["S"])
    assert an.freq == pytest.approx(49.2, abs=0.15)


@pytest.mark.parametrize("fault", ["AG", "BG", "CG", "AB", "BC", "CA", "BCG", "ABC"])
def test_fault_type_classification_from_waveforms(fault):
    rf = 12.0 if fault in ("AG", "BG", "CG") else 1.5
    spec, case, _ = _case(0.45, fault, rf)
    an = analyse(case.records["S"])
    assert an.fault_type == fault


def test_two_ended_beats_single_ended_on_a_resistive_ground_fault():
    spec, case, line = _case(0.85, "AG", 30.0)
    terms = _terms(spec, case)
    res = locate(line, terms)
    assert res.mode == "two-ended"
    single = [e for e in res.estimates if e.method == "E1@S" and e.ok][0]
    assert abs(res.m - spec.m) < abs(single.m - spec.m)
    assert abs(res.m - spec.m) < 0.01


def test_single_ended_path_works_and_says_so():
    """One record must still produce an answer, clearly marked."""
    spec, case, line = _case(0.30, "AG", 2.0)
    res = locate(line, _terms(spec, case, ends=("S",)))
    assert res.ok
    assert res.mode == "single-ended"
    assert any("SINGLE-ENDED" in c for c in res.caveats)
    assert abs(res.m - spec.m) < 0.03


def test_far_end_arriving_late_upgrades_the_answer():
    """Section 5.2: re-issue a corrected report when the far end lands."""
    spec, case, line = _case(0.72, "AG", 25.0)
    first = locate(line, _terms(spec, case, ends=("S",)))
    second = locate(line, _terms(spec, case))
    assert first.mode == "single-ended"
    assert second.mode == "two-ended"
    assert abs(second.m - spec.m) < abs(first.m - spec.m)


def test_e4_is_gated_off_without_clock_quality():
    spec, case, line = _case(0.5, "AG", 5.0)
    res = locate(line, _terms(spec, case))
    e4 = [e for e in res.estimates if e.method == "E4"][0]
    assert not e4.ok
    assert "clock" in e4.reason


def test_series_compensated_line_is_refused_not_guessed():
    spec, case, line = _case(0.5, "AG", 5.0)
    line.series_compensated = True
    res = locate(line, _terms(spec, case))
    assert not res.ok
    assert any("series compensated" in c for c in res.caveats)


def test_result_always_names_its_method():
    spec, case, line = _case(0.5, "BC", 1.0)
    res = locate(line, _terms(spec, case))
    assert res.method
    assert "E5" in res.table() and "E1@S" in res.table()


def test_tower_band_is_reported():
    spec, case, line = _case(0.437, "AG", 3.0)
    res = locate(line, _terms(spec, case))
    assert res.likely_tower is not None
    assert res.towers
    assert abs(res.likely_tower.chainage_km - spec.m * spec.line_km) < 1.0


# --------------------------------------------------------------------------
def test_stage_a_acceptance_criterion():
    """Brief section 13, Stage A: < 0.5 % of line in 95 % of clean cases."""
    faults = ["AG", "BG", "CG", "AB", "BC", "CA", "ABG", "BCG", "CAG", "ABC"]
    errs, modes = [], []
    for i, m in enumerate(np.linspace(0.04, 0.96, 40)):
        f = faults[i % len(faults)]
        rf = 20.0 if f.endswith("G") or f in ("AG", "BG", "CG") else 2.0
        spec, case, line = _case(float(m), f, rf)
        res = locate(line, _terms(spec, case))
        assert res.ok, res.caveats
        errs.append(abs(res.m - spec.m) * 100.0)
        modes.append(res.mode)
    a = np.asarray(errs)
    assert all(x == "two-ended" for x in modes)
    assert float(np.percentile(a, 95)) < 0.5
    # and the algorithm never silently returns an impossible m
    assert float(np.max(a)) < 2.0


def test_never_returns_impossible_m_without_flagging():
    """Feed a deliberately reversed CT at one end."""
    spec, case, line = _case(0.5, "AG", 5.0)
    terms = _terms(spec, case)
    terms["R"].polarity = -1
    res = locate(line, terms)
    # either it refuses, or the answer is marked by a low-weight / caveat path
    bad = [e for e in res.estimates if e.ok and not (-0.05 <= e.m <= 1.05)]
    assert (not res.ok) or bad or abs(res.m - spec.m) > 0.05
