"""Tests for the conclusions engine.

The behaviour worth protecting here is what the engine REFUSES to conclude.
"""
from __future__ import annotations

import os

import pytest

from dranalyser.rules.engine import (CATALOGUE, Rule, RuleError, apply_rules,
                                     evaluate, load_rules)
from dranalyser.rules.signals import infer_zone_operated, map_signals

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M1 = os.path.join(ROOT, "DR & Events 9-4-2026", "Main-1",
                  "26.04.09 03.05.24.000.000.CFG")
M2 = os.path.join(ROOT, "DR & Events 9-4-2026", "Main-2", "DR-1", "DR-1.CFG")
needs_corpus = pytest.mark.skipif(not (os.path.exists(M1) and os.path.exists(M2)),
                                  reason="DHONE corpus not present")


# --------------------------------------------------------------------------
# expression evaluation
# --------------------------------------------------------------------------
def test_unknown_feature_is_an_error_not_a_silent_false():
    """A typo that quietly never fires reads as a healthy network."""
    with pytest.raises(RuleError) as exc:
        evaluate("S_carier_send", {"S_carrier_send": True})
    assert "unknown feature" in str(exc.value)


def test_comparisons_against_missing_values_are_false_not_exceptions():
    f = {"a": None, "b": 5}
    assert evaluate("a > 3", f) is False
    assert evaluate("a < 3", f) is False
    assert evaluate("b > 3", f) is True
    assert evaluate("defined(a)", f) is False
    assert evaluate("defined(b)", f) is True
    assert evaluate("a is None", f) is True


def test_expression_language_refuses_anything_executable():
    for bad in ("__import__('os')", "open('x')", "[].__class__", "lambda: 1",
                "(1).__class__.__bases__"):
        with pytest.raises((RuleError, SyntaxError)):
            evaluate(bad, {})


def test_arithmetic_and_boolean_logic():
    f = {"x": 10.0, "y": 4.0, "on": True, "off": False}
    assert evaluate("x - y > 5", f) is True
    assert evaluate("abs(y - x) == 6", f) is True
    assert evaluate("on and not off", f) is True
    assert evaluate("max(x, y) == 10", f) is True
    assert evaluate("x / 0 > 1", f) is False        # division guarded, not raised


# --------------------------------------------------------------------------
# catalogue integrity
# --------------------------------------------------------------------------
def test_catalogue_loads_and_every_rule_parses():
    rules = load_rules()
    assert len(rules) >= 20
    ids = [r.id for r in rules]
    assert len(ids) == len(set(ids))
    for r in rules:
        assert r.title and r.when and r.action
        assert r.severity in ("info", "investigate", "critical")


def test_every_catalogue_condition_evaluates_against_a_full_feature_set():
    """Guards against a rule referring to a feature that does not exist."""
    from dranalyser.rules.features import incident_features
    from tests.helpers import synthetic_incident            # noqa: F401

    feats = synthetic_incident()
    res = apply_rules(feats, load_rules())
    assert not res.errors, res.errors


def test_a_rule_with_a_bad_severity_is_rejected():
    with pytest.raises(RuleError):
        Rule(id="X", title="t", severity="urgent", when="True")


# --------------------------------------------------------------------------
# the requires mechanism
# --------------------------------------------------------------------------
def test_missing_required_feature_is_reported_not_passed():
    rules = [Rule(id="T-01", title="Carrier check", severity="critical",
                  requires=["R_carrier_recv_mapped"],
                  when="S_carrier_send and not R_carrier_recv",
                  action="check the channel")]
    feats = {"S_carrier_send": True, "R_carrier_recv": False,
             "R_carrier_recv_mapped": False}
    res = apply_rules(feats, rules)
    assert not res.findings
    assert len(res.skipped) == 1
    assert "not a healthy result" in res.skipped[0].reason
    assert res.verdict == "Correct operation"      # but the skip is visible


def test_location_rules_are_skipped_when_no_location_exists():
    rules = [Rule(id="T-02", title="Reach check", severity="critical",
                  needs_location=True, when="m > 0.85", action="a")]
    res = apply_rules({"location_available": False, "m": None}, rules)
    assert not res.findings
    assert res.skipped and "needs a fault location" in res.skipped[0].reason


def test_verdict_rolls_up_by_worst_severity():
    mk = lambda i, s: Rule(id=i, title=i, severity=s, when="True", action="a")
    assert apply_rules({}, [mk("A", "info")]).verdict == "Correct operation"
    assert apply_rules({}, [mk("B", "investigate")]).verdict == "Correct but investigate"
    assert apply_rules({}, [mk("C", "critical"), mk("D", "info")]).verdict == \
        "Incorrect operation"


def test_message_renders_even_when_half_the_values_are_missing():
    rules = [Rule(id="T-03", title="t", severity="info", when="True",
                  message="S={S_breaker_ms:.0f} ms and R={R_breaker_ms:.0f} ms",
                  action="a")]
    res = apply_rules({"S_breaker_ms": 47.3, "R_breaker_ms": None}, rules)
    assert res.findings[0].message == "S=47 ms and R=n/a ms"


# --------------------------------------------------------------------------
# signal mapping
# --------------------------------------------------------------------------
def test_scored_mapping_prefers_the_distance_element_over_overcurrent():
    """A SIPROTEC offers ten trip channels; the first regex hit is the wrong one."""
    chans = ["O/C TRIP 1p.L1", "O/C TRIP I>>", "Dis.Gen. Trip", "Relay TRIP",
             "EF 3I0> TRIP", ">1p Trip Perm"]
    m = map_signals(chans)
    assert m.channel("TRIP") == "Dis.Gen. Trip"
    assert len(m.channels("TRIP")) > 1


def test_general_pickup_wins_over_the_earth_starter():
    m = map_signals(["O/C PICKUP", "Dis.Pickup L1", "Dis.Pickup E", "Relay PICKUP"])
    assert m.channel("START") == "Relay PICKUP"


def test_carrier_send_and_receive_are_separated():
    m = map_signals(["Dis.T.SEND L1", ">DisTel Rec.Ch1", "Dis.T.Carr.Fail"])
    assert m.channel("CARRIER_SEND") == "Dis.T.SEND L1"
    assert m.channel("CARRIER_RECV") == ">DisTel Rec.Ch1"
    assert m.channel("CARRIER_FAIL") == "Dis.T.Carr.Fail"


def test_recorder_housekeeping_channels_are_ignored_not_mapped():
    m = map_signals([">Trig.Wave.Cap.", "Flag Lost", "Fault rec. run.", "Unused"])
    assert not m.candidates
    assert len(m.ignored) == 4


def test_zone_inference_does_not_claim_zone_1_it_cannot_prove():
    """A fast trip is Zone 1 OR an aided Zone 2, and timing cannot separate them."""
    assert infer_zone_operated({}, 0.020, z2_time_s=0.45) == "Z1_OR_AIDED"
    assert infer_zone_operated({"TRIP_Z2": 0.5}, 0.020) == "Z2"
    assert infer_zone_operated({"TRIP_Z3": 0.9}, 0.9) == "Z3"
    assert infer_zone_operated({}, None) is None


# --------------------------------------------------------------------------
# against the real records
# --------------------------------------------------------------------------
@needs_corpus
def test_carrier_rule_is_not_evaluable_on_a_relay_with_no_send_channel():
    """Main-1 records a carrier receive but no carrier send.

    CR-01 is the highest-value rule in the catalogue and it simply cannot be
    judged from this relay as configured. Reporting that is the point.
    """
    from tests.helpers import real_incident

    feats = real_incident(M1)
    res = apply_rules(feats, load_rules())
    skipped = {s.rule_id for s in res.skipped}
    assert "CR-01" in skipped
    reason = [s.reason for s in res.skipped if s.rule_id == "CR-01"][0]
    assert "S_carrier_send_mapped" in reason


@needs_corpus
def test_main_1_verdict_is_incorrect_operation_because_of_the_vt():
    from tests.helpers import real_incident

    res = apply_rules(real_incident(M1), load_rules())
    assert res.verdict == "Incorrect operation"
    assert any(f.rule_id == "MS-04" for f in res.findings)


@needs_corpus
def test_breaker_timing_agrees_between_the_two_relays():
    """Same breaker, two independent recorders, different sample rates."""
    from tests.helpers import real_incident

    a, b = real_incident(M1), real_incident(M2)
    assert a["S_pole_open_a_ms"] == pytest.approx(b["S_pole_open_a_ms"], abs=3.0)
    assert 30.0 < a["S_breaker_ms"] < 70.0
    assert 30.0 < b["S_breaker_ms"] < 70.0


@needs_corpus
def test_pole_discrepancy_is_not_judged_on_a_single_pole_trip():
    from tests.helpers import real_incident

    res = apply_rules(real_incident(M2), load_rules())
    assert not any(f.rule_id == "CB-02" for f in res.findings)
    assert any(s.rule_id == "CB-02" for s in res.skipped)


# --------------------------------------------------------------------------
# backup overcurrent / earth fault
# --------------------------------------------------------------------------
def test_backup_elements_map_to_their_own_signals_not_to_the_distance_trip():
    m = map_signals(["O/C PICKUP", "O/C TRIP I>>", "EF Pickup", "EF 3I0> TRIP",
                     "Dis.Gen. Trip", "Relay PICKUP"])
    assert m.channel("OC_PICKUP") == "O/C PICKUP"
    assert m.channel("OC_TRIP") == "O/C TRIP I>>"
    assert m.channel("EF_PICKUP") == "EF Pickup"
    assert m.channel("EF_TRIP") == "EF 3I0> TRIP"
    # and the distance trip is still the distance trip
    assert m.channel("TRIP") == "Dis.Gen. Trip"


def test_backup_clearing_the_fault_is_a_critical_finding():
    rules = [r for r in load_rules() if r.id in ("BU-01", "BU-02")]
    feats = {"S_backup_operated": True, "R_backup_operated": False,
             "S_backup_trip_ms": 820.0, "R_backup_trip_ms": None,
             "S_backup_before_distance": False, "R_backup_before_distance": False,
             "S_backup_grading_ms": 400.0, "S_trip_ms": 420.0,
             "S_oc_trip_ms": 820.0, "S_ef_trip_ms": None,
             "S_oc_setting_time_s": 0.8}
    res = apply_rules(feats, rules)
    assert any(f.rule_id == "BU-01" for f in res.findings)
    assert res.verdict == "Incorrect operation"


def test_backup_racing_the_distance_element_is_flagged():
    rules = [r for r in load_rules() if r.id == "BU-02"]
    feats = {"S_backup_before_distance": True, "R_backup_before_distance": False,
             "S_backup_grading_ms": -5.0, "S_backup_trip_ms": 25.0,
             "S_trip_ms": 30.0, "S_oc_setting_time_s": 0.0}
    assert apply_rules(feats, rules).findings[0].rule_id == "BU-02"


@needs_corpus
def test_real_record_shows_backup_grading_holding():
    """EF picked up at +25 ms and reset when distance cleared at +79 ms."""
    from tests.helpers import real_incident

    f = real_incident(M2)
    assert f["S_ef_pickup"] is True
    assert f["S_ef_trip"] is False
    assert f["S_backup_operated"] is False
    assert f["S_backup_picked_up"] is True
    res = apply_rules(f, load_rules())
    assert any(x.rule_id == "BU-04" for x in res.findings)
    assert not any(x.rule_id in ("BU-01", "BU-02") for x in res.findings)


@needs_corpus
def test_real_record_flags_the_disabled_earth_fault_stage():
    from tests.helpers import real_incident

    f = real_incident(M2)
    assert f["S_ef_stage_disabled"] is True
    assert f["S_oc_stage_disabled"] is False
    assert f["S_oc_setting_a"] == pytest.approx(1600.0)
    res = apply_rules(f, load_rules())
    assert any(x.rule_id == "BU-03" for x in res.findings)


@needs_corpus
def test_real_record_questions_the_silent_overcurrent_stage():
    """7.1 kA against a 1600 A pickup, with no overcurrent pickup recorded."""
    from tests.helpers import real_incident

    f = real_incident(M2)
    assert f["S_i_fault_over_oc_setting"] > 4.0
    assert f["S_oc_pickup"] is False
    res = apply_rules(f, load_rules())
    assert any(x.rule_id == "BU-05" for x in res.findings)
