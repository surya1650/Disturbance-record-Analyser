"""Tests for the Stage-A acceptance sweep.

The sweep itself is slow, so the suite runs a small serial one. The full
10^4-10^5 run is `dranalyse stage-a`, and its measured result is recorded in
the README rather than asserted here.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from dranalyser import stagea
from dranalyser.faultloc.ensemble import TerminalInput, locate
from dranalyser.faultloc.estimators import e5_unsynchronised
from dranalyser.dsp.detect import classify_fault
from dranalyser.dsp.pipeline import analyse
from dranalyser.registry.model import uniform_line
from dranalyser.stagea import CaseResult, Summary, _sample, run_case
from dranalyser.synth.generator import SynthSpec, TerminalSpec, generate


# --------------------------------------------------------------------------
# defects the wide sweep found, locked in
# --------------------------------------------------------------------------
def test_classifier_declines_rather_than_crashing_on_non_finite_phasors():
    """A degenerate window produced NaN and killed 6 % of the sweep."""
    nan = complex(float("nan"), float("nan"))
    kind, diag = classify_fault(nan, nan, nan, 0j)
    assert kind == "NONE"
    assert all(math.isfinite(v) for v in diag.values())
    kind, _ = classify_fault(complex(1, 0), nan, complex(0.1, 0), 0j)
    assert kind == "NONE"


def test_e5_refuses_a_root_far_outside_the_line():
    """m = 6.7 pu is corrupt input, not a remote fault."""
    z1 = complex(3.0, 40.0)
    # inconsistent terminals: the magnitudes cannot be reconciled anywhere near
    # the line, which is what a saturated CT does to E5
    v2s = complex(4000.0, 0.0)
    i2s = complex(10.0, -2.0)
    v2r = complex(80.0, 5.0)
    i2r = complex(0.4, 0.05)
    est = e5_unsynchronised([v2s] * 6, [i2s] * 6, [v2r] * 6, [i2r] * 6, z1)
    if est.ok:
        assert -0.5 <= est.m <= 1.5
    else:
        assert "no root near the line" in est.reason


@pytest.mark.parametrize("invalid_m", [-5.7, -0.5001, 1.5001, 6.7])
def test_ensemble_refuses_to_report_a_distance_far_outside_the_line(monkeypatch, invalid_m):
    from dranalyser.faultloc import ensemble
    from dranalyser.faultloc.estimators import Estimate

    line = uniform_line("T", "t", 220, 100, complex(0.03, 0.4), complex(0.25, 1.2))
    spec = SynthSpec(m=0.4, fault="AG", rf=1.0)
    case = generate(spec)
    an = analyse(case.records["S"])
    ti = TerminalInput(analysed=an, end="S")
    # Inject BEFORE real weighting/reconciliation; never edit a finished result.
    supplied = Estimate("E1", invalid_m, 0.0, ends="single")
    monkeypatch.setattr(ensemble, "_single_ended", lambda *args: [supplied])
    assert line.towers, "a missing tower schedule would make suppression vacuous"
    res = locate(line, {"S": ti})
    assert supplied in res.estimates
    assert supplied.diagnostics["weight"] > 0  # reaches the final distance guard
    assert res.mode == "none" and not res.ok
    assert res.m == pytest.approx(invalid_m)  # diagnostic retained, never clamped
    assert math.isnan(res.km_from_S) and math.isnan(res.km_from_R)
    assert all(math.isnan(km) for km in res.interval_km)
    assert res.towers == [] and res.likely_tower is None
    assert any("far outside the line; no location is reported" in c for c in res.caveats)


def test_absurd_m_never_reaches_a_tower_band():
    """Whatever else happens, a tower must not be named from a corrupt m."""
    summ = stagea.run(cases=120, workers=1, seed=4)
    for r in summ.results:
        if r.ok and math.isfinite(r.m_est):
            assert -0.5 <= r.m_est <= 1.5, (r.seed, r.fault, r.m_est)
    assert not any(r.impossible_unflagged for r in summ.results)


# --------------------------------------------------------------------------
# the sweep itself
# --------------------------------------------------------------------------
def test_sampled_parameters_stay_inside_the_documented_envelope():
    rng = np.random.default_rng(0)
    for i in range(400):
        p = _sample(rng, i)
        assert 0.02 <= p["m"] <= 0.98
        assert p["fault"] in stagea.FAULTS
        assert 0.09 <= p["rf"] <= 61.0
        assert 0.09 <= p["sir_s"] <= 31.0
        assert p["fs_s"] in stagea.SAMPLE_RATES
        assert p["adc_bits"] in (12, 14, 16)
        assert 0.0 <= p["inception_deg"] <= 360.0


def test_condition_buckets_are_mutually_consistent():
    r = CaseResult(seed=0, m_true=0.5, fault="AG", rf=40.0, sir_s=1.0, sir_r=1.0,
                   inception_deg=0.0, fs_s=1000.0, fs_r=1000.0, saturated=False,
                   adc_bits=12, window_cycles=2.0)
    assert r.high_rf and not r.clean
    r.rf = 1.0
    assert not r.high_rf and r.clean
    r.saturated = True
    assert not r.clean
    r.saturated = False
    r.sir_r = 20.0
    assert r.weak_infeed and not r.clean
    r.sir_r = 1.0
    r.window_cycles = 0.6
    assert r.short_window and not r.clean


def test_phase_fault_high_rf_threshold_is_not_the_ground_one():
    """4 ohm is a lot between phases and nothing to earth."""
    g = CaseResult(seed=0, m_true=0.5, fault="AG", rf=10.0, sir_s=1, sir_r=1,
                   inception_deg=0, fs_s=1000, fs_r=1000, saturated=False,
                   adc_bits=12, window_cycles=2.0)
    p = CaseResult(seed=0, m_true=0.5, fault="BC", rf=10.0, sir_s=1, sir_r=1,
                   inception_deg=0, fs_s=1000, fs_r=1000, saturated=False,
                   adc_bits=12, window_cycles=2.0)
    assert not g.high_rf
    assert p.high_rf


def test_a_small_sweep_runs_and_lands_in_the_right_ballpark():
    """Deliberately does NOT assert the 0.5 % p95 criterion.

    Over ~50 clean cases the 95th percentile is one of the worst two or three
    values and swings by a factor of two between seeds -- asserting it here
    would be asserting noise, which is how a suite comes to fail for reasons
    nobody can act on. The criterion belongs to `dranalyse stage-a` at 10^4
    cases, where it is stable. What is asserted here is that the machinery
    runs and the central tendency is where it should be.
    """
    summ = stagea.run(cases=150, workers=1, seed=2)
    assert len(summ.results) == 150
    located = summ.subset("all")
    assert len(located) > 130, "too many cases failed to produce an answer"
    clean = summ.stats(summ.subset("clean"))
    assert clean["n"] > 30
    assert clean["mean"] < 0.30
    assert clean["p50"] < 0.20
    assert not any(r.impossible_unflagged for r in summ.results)


def test_the_sweep_is_reproducible_for_a_given_seed():
    a = stagea.run(cases=40, workers=1, seed=3)
    b = stagea.run(cases=40, workers=1, seed=3)
    for x, y in zip(a.results, b.results):
        assert x.seed == y.seed and x.fault == y.fault
        assert x.m_true == pytest.approx(y.m_true)
        if math.isfinite(x.err_pct) or math.isfinite(y.err_pct):
            assert x.err_pct == pytest.approx(y.err_pct, nan_ok=True)


def test_an_unflagged_impossible_result_fails_the_criterion():
    """The criterion is not only accuracy: silence about nonsense fails too.

    Built from constructed results rather than a real sweep, so it tests the
    rule and not whichever seed happened to be drawn.
    """
    def case(err: float, impossible: bool = False) -> CaseResult:
        r = CaseResult(seed=0, m_true=0.5, fault="AG", rf=1.0, sir_s=1.0,
                       sir_r=1.0, inception_deg=0.0, fs_s=1000.0, fs_r=1000.0,
                       saturated=False, adc_bits=12, window_cycles=2.0)
        r.ok, r.err_pct, r.m_est = True, err, 0.5
        r.impossible_unflagged = impossible
        return r

    good = Summary(results=[case(0.1) for _ in range(50)])
    assert good.passed()

    # accuracy fine, but one absurd answer went out without a caveat
    silent = Summary(results=[case(0.1) for _ in range(49)] + [case(0.1, True)])
    assert not silent.passed()

    # accuracy alone can also fail it
    inaccurate = Summary(results=[case(0.1) for _ in range(45)]
                         + [case(3.0) for _ in range(5)])
    assert not inaccurate.passed()


def test_report_shows_both_clean_and_everything():
    """Quoting only the clean figure describes a system nobody recognises."""
    summ = stagea.run(cases=80, workers=1, seed=8)
    text = summ.report()
    assert "clean data" in text and "everything" in text
    assert "BY SAMPLE RATE" in text
    assert "BY FAULT TYPE" in text
    assert "TWO-ENDED AGAINST SINGLE-ENDED" in text
    assert "STAGE-A CRITERION" in text


def test_two_ended_beats_single_ended_across_the_sweep():
    summ = stagea.run(cases=200, workers=1, seed=9)
    both = [r for r in summ.subset("all")
            if math.isfinite(r.e5_err_pct) and math.isfinite(r.single_err_pct)]
    assert len(both) > 100
    better = sum(1 for r in both if r.e5_err_pct < r.single_err_pct)
    assert better / len(both) > 0.6


def test_csv_export_carries_the_condition_columns(tmp_path):
    import csv

    summ = stagea.run(cases=30, workers=1, seed=10)
    out = tmp_path / "sa.csv"
    summ.to_csv(str(out))
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 30
    for col in ("m_true", "err_pct", "clean", "high_rf", "weak_infeed",
                "short_window", "saturated"):
        assert col in rows[0]
