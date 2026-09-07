"""Tests for the learning layer.

The point of these is as much what the models REFUSE to do as what they do.
"""
from __future__ import annotations

import copy

import numpy as np
import pytest

from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc.ensemble import TerminalInput, locate
from dranalyser.ml.tier1 import Observation, apply_k0, estimate_k0
from dranalyser.ml.tier2 import (CAP_FRACTION, CAP_KM, GroundTruthEvent,
                                 ResidualModel, leave_one_line_out)
from dranalyser.ml.tier3 import (fault_features, saturation_features,
                                 second_opinion, train_ct_saturation,
                                 train_fault_type)
from dranalyser.registry.model import k0_from_impedances, uniform_line
from dranalyser.synth.generator import SynthSpec, TerminalSpec, generate


def _incident(m, fault="AG", rf=5.0, seed=0):
    spec = SynthSpec(
        m=m, fault=fault, rf=rf, seed=seed,
        S=TerminalSpec(fs=1000.0, prefault_s=0.12, post_s=0.25, breaker_time_s=0.060),
        R=TerminalSpec(fs=1200.0, prefault_s=0.16, post_s=0.25, breaker_time_s=0.060,
                       sample_phase=0.37, clock_offset_s=1418.0),
    )
    case = generate(spec)
    line = uniform_line("L", "l", spec.kv, spec.line_km, spec.z1_per_km,
                        spec.z0_per_km, spec.zs1_S, spec.zs0_S, spec.zs1_R, spec.zs0_R)
    terms = {e: TerminalInput(analysed=analyse(case.records[e]), end=e,
                              zs1=spec.zs1_S if e == "S" else spec.zs1_R,
                              zs0=spec.zs0_S if e == "S" else spec.zs0_R)
             for e in ("S", "R")}
    return spec, case, line, terms


# --------------------------------------------------------------------------
# Tier 1
# --------------------------------------------------------------------------
def test_tier1_recovers_a_deliberately_wrong_zero_sequence_impedance():
    """The whole argument for Tier 1: Z0 is routinely 10-20 % wrong.

    E5 supplies m without using any zero-sequence data, which leaves k0 as
    the only unknown in the single-ended ground-loop equation. No patrol
    confirmation is needed.
    """
    obs = []
    true_line = None
    for i, m in enumerate((0.25, 0.45, 0.65, 0.80)):
        spec, case, line, terms = _incident(m, "AG", rf=3.0, seed=i)
        true_line = line
        res = locate(line, terms)
        assert res.mode == "two-ended"
        obs.append(Observation(m=res.m, fault="AG",
                               terminals={e: t.analysed for e, t in terms.items()}))

    wrong = copy.deepcopy(true_line)
    for s in wrong.sections:            # Z0 entered 22 % high, as happens
        s.r0 *= 1.22
        s.x0 *= 1.22

    est = estimate_k0(obs, wrong)
    k0_true = k0_from_impedances(true_line.z1, true_line.z0)
    assert est.accepted, est.reason
    # the fit must move k0 substantially towards the truth
    err_before = abs(est.k0_registry - k0_true) / abs(k0_true)
    err_after = abs(est.k0 - k0_true) / abs(k0_true)
    assert err_before > 0.15
    assert err_after < 0.25 * err_before

    fixed = apply_k0(wrong, est)
    assert abs(abs(fixed.z0) - abs(true_line.z0)) / abs(true_line.z0) < 0.05


def test_tier1_refuses_a_single_event():
    spec, case, line, terms = _incident(0.4)
    obs = [Observation(m=0.4, fault="AG",
                       terminals={e: t.analysed for e, t in terms.items()})]
    est = estimate_k0(obs, line)
    assert not est.accepted
    assert "at least" in est.reason


def test_tier1_rejects_an_implausible_jump():
    """A huge implied change means a ratio or polarity error, not a wrong Z0."""
    obs = []
    for i, m in enumerate((0.3, 0.6)):
        spec, case, line, terms = _incident(m, "AG", rf=3.0, seed=i)
        obs.append(Observation(m=m, fault="AG",
                               terminals={e: t.analysed for e, t in terms.items()}))
    silly = copy.deepcopy(line)
    for s in silly.sections:
        s.r0 *= 6.0
        s.x0 *= 6.0
    est = estimate_k0(obs, silly)
    assert not est.accepted
    assert "sanity limit" in est.reason


# --------------------------------------------------------------------------
# Tier 2
# --------------------------------------------------------------------------
def _events(n, n_lines=8, bias=0.01, seed=0, feature_driven=True):
    """Synthetic ground truth with the structure Tier 2 is designed to find.

    The residual has three parts, as it does in reality: a fleet-wide offset,
    a part driven by features that ARE available at prediction time (fault
    resistance, reach non-linearity, window length), and a per-line part.
    Only the first two can transfer to a held-out line, which is exactly what
    leave-one-line-out is meant to measure.
    """
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        lid = "LINE-" + str(i % n_lines)
        m_true = float(rng.uniform(0.05, 0.95))
        rf = float(rng.uniform(0, 30))
        win = float(rng.uniform(1.0, 4.0))
        per_line = 0.002 * ((i % n_lines) - n_lines / 2.0)
        feat = (0.0006 * rf + 0.020 * (m_true - 0.5) ** 2 - 0.003 * win) \
            if feature_driven else 0.0
        m_model = m_true - (bias + per_line + feat) - float(rng.normal(0, 0.002))
        out.append(GroundTruthEvent(
            line_id=lid, m_true=m_true, m_model=m_model, line_km=100.0,
            features={"rf_ohm": rf, "sir_S": 1.0,
                      "sir_R": 1.0, "load_angle_deg": 10.0, "r2_over_r1": 0.9,
                      "sat_S": 0.0, "sat_R": 0.0, "window_cycles": win,
                      "is_ground": 1.0, "is_three_phase": 0.0,
                      "season_sin": 0.0, "season_cos": 1.0}))
    return out


def test_tier2_is_gated_below_one_hundred_confirmed_events():
    m = ResidualModel().fit(_events(40))
    assert not m.fitted
    assert "gated" in m.reason
    c = m.correct(0.5, "LINE-0", 100.0, {})
    assert not c.applied
    assert c.m_corrected == 0.5           # physics answer untouched


def test_tier2_fits_and_helps_once_the_gate_is_passed():
    ev = _events(240)
    m = ResidualModel().fit(ev)
    assert m.fitted
    before = float(np.mean([abs(e.m_true - e.m_model) for e in ev]))
    after = float(np.mean([
        abs(e.m_true - m.correct(e.m_model, e.line_id, e.line_km, e.features).m_corrected)
        for e in ev]))
    assert after < before


def test_tier2_correction_is_capped_and_always_reports_the_raw_value():
    ev = _events(240, bias=0.35)          # an absurd systematic
    m = ResidualModel().fit(ev)
    c = m.correct(0.5, "LINE-0", 300.0, ev[0].features)
    assert c.capped
    cap = min(CAP_FRACTION, CAP_KM / 300.0)
    assert abs(c.delta_pu) <= cap + 1e-12
    # on a 300 km line the brief's flat 2 % would be 6 km; the absolute cap bites
    assert abs(c.delta_pu) * 300.0 <= CAP_KM + 1e-9
    assert c.m_raw == 0.5


def test_tier2_validation_is_leave_one_line_out_and_can_say_no():
    ev = _events(240)
    v = leave_one_line_out(ev)
    assert v.n_lines == 8
    assert v.mae_model_pu < v.mae_raw_pu
    assert v.ships, v.reason
    assert v.relative_gain > 0.10
    assert v.gain_ci_low > 0.0

    # pure noise, no learnable structure: it must refuse to ship
    rng = np.random.default_rng(1)
    noise = [GroundTruthEvent(line_id="L" + str(i % 6),
                              m_true=float(rng.uniform(0.1, 0.9)),
                              m_model=float(rng.uniform(0.1, 0.9)),
                              line_km=100.0, features={})
             for i in range(200)]
    assert not leave_one_line_out(noise).ships


# --------------------------------------------------------------------------
# Tier 3
# --------------------------------------------------------------------------
@pytest.mark.slow
def test_tier3_fault_type_classifier_trains_on_synthetic_labels():
    model = train_fault_type(n_per_class=8, seed=3)
    assert model.metrics["n_samples"] > 100
    assert model.metrics["cv_accuracy"] > 0.75


@pytest.mark.slow
def test_tier3_ct_saturation_detector_trains_on_synthetic_labels():
    model = train_ct_saturation(n_cases=60, seed=4)
    assert model.metrics["cv_accuracy"] > 0.80


def test_tier3_features_are_finite_on_a_real_shaped_record():
    spec, case, line, terms = _incident(0.4, "AG")
    f = fault_features(terms["S"].analysed)
    assert all(np.isfinite(v) for v in f.values())
    rec = case.records["S"]
    n = int(round(rec.fs / rec.line_freq))
    lo = int(0.12 * rec.fs) + n // 4
    g = saturation_features(rec.analog["IA"], rec.fs, rec.line_freq, lo, lo + 3 * n)
    assert all(np.isfinite(v) for v in g.values())


def test_tier3_is_only_a_second_opinion():
    """A missing or silent model must never change the physics answer."""
    spec, case, line, terms = _incident(0.4, "AG")
    an = terms["S"].analysed
    assert second_opinion(an, None) is None
    assert an.fault_type == "AG"
