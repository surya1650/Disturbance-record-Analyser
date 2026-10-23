"""Frozen-cohort accounting and end-to-end replay use explicitly synthetic truth."""

import copy
import hashlib
import json
from datetime import datetime, timezone

import pytest

from dranalyser.cli import main
from dranalyser.comtrade.parser import read_comtrade
from dranalyser.validation.acceptance import evaluate
from dranalyser.validation.replay import replay, template
from scripts.create_demo import create_demo


def protocol(ids=("A", "B")):
    return {
        "name": "Synthetic unit-test protocol only",
        "frozen_at": "2026-01-01T00:00:00Z",
        "planned_event_ids": list(ids),
        "training_line_ids": [],
        "min_events": len(ids),
        "max_p95_error_pct": 0.5,
        "min_located_fraction": 0.95,
    }


def outcome(event_id="A"):
    return {
        "event_id": event_id,
        "line_id": "L",
        "record_hashes": [hashlib.sha256(event_id.encode()).hexdigest()],
        "line_km": 100.0,
        "truth_km": 50.0,
        "truth_uncertainty_km": 0.02,
        "estimated_km": 50.1,
        "diagnostic_interval_km": [49.8, 50.3],
        "evidence_verified": True,
        "executed_at": "2026-10-23T00:00:00Z",
    }


def test_empty_protocol_cannot_pass_and_has_no_fabricated_metrics():
    out = evaluate(template()["protocol"], [])
    assert out["status"] == "not_ready" and out["total_events"] == 0
    assert out["p95_error_pct"] is out["located_fraction"] is None


def test_uncertain_truth_and_coverage_are_descriptive_with_explicit_denominators():
    cases = [outcome("A"), outcome("B")]
    cases[1].update(estimated_km=50.3, diagnostic_interval_km=[50.1, 50.4])
    out = evaluate(protocol(), cases)
    assert out["status"] == "pass"
    assert out["eligible_events"] == out["located_events"] == 2
    assert out["p95_error_pct"] == pytest.approx(0.29)
    assert out["p95_worst_case_error_pct"] == pytest.approx(0.31)
    assert out["diagnostic_interval_contains_truth_fraction"] == 0.5
    assert out["diagnostic_interval_cases"] == 2
    assert "not calibrated" in out["limits"]


def test_refusals_remain_in_the_cohort_and_cannot_improve_pass_through_a_lower_tail():
    cases = [outcome("A"), outcome("B")]
    cases[1]["estimated_km"] = None
    out = evaluate(protocol(), cases)
    assert out["status"] == "fail"
    assert out["refused_events"] == 1 and out["located_fraction"] == 0.5
    assert out["within_threshold_fraction_all_eligible"] == 0.5


def test_uncertainty_can_fail_the_conservative_error_gate():
    case = outcome()
    case["truth_uncertainty_km"] = 1
    out = evaluate(protocol(("A",)), [case])
    assert out["status"] == "fail" and out["p95_error_pct"] < 0.5
    assert out["p95_worst_case_error_pct"] > 0.5


@pytest.mark.parametrize(
    "case",
    [
        "duplicate_event",
        "reused_record",
        "same_terminal_record",
        "training_line",
        "missing_truth",
        "nan_truth",
        "outside",
        "negative_uncertainty",
        "unreviewed",
        "prior_execution",
        "missing_execution",
        "bad_interval",
    ],
)
def test_invalid_or_leaky_cases_are_explicitly_withheld(case):
    cases = [outcome("A"), outcome("B")]
    p = protocol()
    if case == "duplicate_event":
        cases[1]["event_id"] = "A"
    if case == "reused_record":
        cases[1]["record_hashes"] = cases[0]["record_hashes"]
    if case == "same_terminal_record":
        cases[1]["record_hashes"] *= 2
    if case == "training_line":
        p["training_line_ids"] = ["L"]
    if case == "missing_truth":
        cases[1]["truth_km"] = None
    if case == "nan_truth":
        cases[1]["truth_km"] = float("nan")
    if case == "outside":
        cases[1]["estimated_km"] = 101
    if case == "negative_uncertainty":
        cases[1]["truth_uncertainty_km"] = -0.1
    if case == "unreviewed":
        cases[1]["evidence_verified"] = False
    if case == "prior_execution":
        cases[1]["executed_at"] = "2025-01-01T00:00:00Z"
    if case == "missing_execution":
        cases[1]["executed_at"] = ""
    if case == "bad_interval":
        cases[1]["diagnostic_interval_km"] = [51, 49]
    before = copy.deepcopy(cases)
    out = evaluate(p, cases)
    if case == "bad_interval":
        assert out["status"] == "pass" and out["diagnostic_interval_cases"] == 1
        assert out["cases"][1]["diagnostic_interval_issue"]
    else:
        assert out["status"] == "not_ready" and out["excluded_events"] >= 1
    if case != "nan_truth":
        assert cases == before


def manifest(tmp_path):
    root = create_demo(tmp_path / "SYNTHETIC")

    def proof(path):
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    review_path, truth_path = root / "review.txt", root / "truth.txt"
    review_path.write_text("SYNTHETIC TEST declarations, not field evidence.")
    truth_path.write_text("SYNTHETIC fault location m=.42 on a 62 km simulated line. Not patrol truth.")
    confirmations = (
        "same_incident_and_stage",
        "terminal_identity",
        "phase_mapping",
        "ct_vt_scaling_and_polarity",
        "event_effective_line_and_topology",
        "independent_patrol_truth",
    )
    data = {
        "schema": "dranalyser.field-acceptance.v1",
        "protocol": protocol(("A",)),
        "cases": [
            {
                "event_id": "A",
                "line": proof(root / "synthetic-line.yaml"),
                "review": {**proof(review_path), "reviewer": "Synthetic test", **dict.fromkeys(confirmations, True)},
                "truth": {**proof(truth_path), "chainage_km": 0.42 * 62, "uncertainty_km": 0.1, "independent": True},
                "records": {
                    e: {
                        "path": str(root / e / "event.cfg"),
                        "record_hash": read_comtrade(str(root / e / "event.cfg")).content_hash,
                    }
                    for e in ("S", "R")
                },
            }
        ],
    }
    # The test fixture's generated line length is authoritative for its synthetic truth.
    import yaml

    length = yaml.safe_load((root / "synthetic-line.yaml").read_text())["sections"][0]["to_km"]
    data["cases"][0]["truth"]["chainage_km"] = 0.42 * length
    file = root / "manifest.json"
    file.write_text(json.dumps(data))
    return file, data


def test_replay_executes_existing_solver_preserves_sources_and_binds_protocol(tmp_path):
    path, data = manifest(tmp_path)
    before = {p: p.read_bytes() for p in path.parent.rglob("*") if p.is_file()}
    out = replay(path)
    assert out["eligible_events"] == 1, out
    assert out["located_events"] == 1 and "E5" in out["cases"][0]["method"]
    assert abs(out["cases"][0]["estimated_km"] - data["cases"][0]["truth"]["chainage_km"]) < 0.3
    assert out["manifest_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert out["protocol_hash"] and datetime.fromisoformat(out["cases"][0]["executed_at"]).tzinfo == timezone.utc
    assert before == {p: p.read_bytes() for p in path.parent.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "mutation", ["line_hash", "record_hash", "unreviewed", "truth_hash", "not_independent", "same_record"]
)
def test_replay_does_not_trust_modified_or_undeclared_inputs(tmp_path, mutation):
    path, data = manifest(tmp_path)
    case = data["cases"][0]
    if mutation == "line_hash":
        case["line"]["sha256"] = "0" * 64
    if mutation == "record_hash":
        case["records"]["R"]["record_hash"] = "0" * 64
    if mutation == "unreviewed":
        case["review"]["terminal_identity"] = False
    if mutation == "truth_hash":
        case["truth"]["sha256"] = "0" * 64
    if mutation == "not_independent":
        case["truth"]["independent"] = False
    if mutation == "same_record":
        case["records"]["R"] = case["records"]["S"]
    path.write_text(json.dumps(data))
    out = replay(path)
    assert out["status"] == "not_ready" and out["excluded_events"] == 1


def test_cli_empty_manifest_stays_not_ready_and_does_not_create_confirmations(tmp_path):
    form, report = tmp_path / "protocol.json", tmp_path / "result.json"
    assert main(["acceptance", "--template", "--out", str(form)]) == 0
    assert main(["acceptance", "--manifest", str(form), "--out", str(report)]) == 2
    out = json.loads(report.read_text())
    assert out["status"] == "not_ready" and not out["cases"]
    assert not list(tmp_path.glob("*.db"))
