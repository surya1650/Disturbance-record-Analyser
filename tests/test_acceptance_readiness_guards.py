"""Prevent unverified candidates, settings gaps and unusable truth enabling claims."""

import copy

import pytest

from dranalyser.faultloc.model_domain import scalar_model_reasons
from dranalyser.groundtruth import Confirmation, Store
from dranalyser.registry.catalogue import build_catalogue, digest
from dranalyser.registry.catalogue_review import source_candidate
from dranalyser.registry.loader import line_from_dict, load_line
from dranalyser.registry.model import Relay, RelaySetting
from tests.test_source_catalogue import snapshot
from tests.test_stage_location import line as stage_line, reviewed_pair
from dranalyser.faultloc.stage_location import stage_e5
from dranalyser.faultloc.ensemble import locate, TerminalInput


def selection(cat):
    return {
        "catalogue_hash": digest(cat),
        "line_id": "SYNTHETIC",
        "identity_confirmation": "Synthetic unit test explicit S/R identity",
        "impedance_basis": "primary_total_ohm",
        "basis_interpretation": "Synthetic specified source units",
        "terminals": {"S": cat["rows"][0]["id"], "R": cat["rows"][1]["id"]},
    }


def test_identified_source_candidate_retains_values_but_refuses_unreviewed_model():
    cat = build_catalogue(snapshot())
    before = copy.deepcopy(cat)
    candidate = source_candidate(cat, selection(cat), {"tower_span_km": 0.35})
    assert candidate["model_review_required"] is True
    assert candidate["sections"][0]["to_km"] == 20
    assert candidate["towers"] == [] and "tower_span_km" not in candidate
    model = line_from_dict(candidate)
    assert model.z1 == 2 + 8j and not model.towers
    assert "review remains required" in " ".join(scalar_model_reasons(model))
    assert cat == before and not candidate["source_provenance"]["field_verified"]


def test_review_required_cannot_bypass_main_or_stage_location():
    model = stage_line()
    model.model_review_required = True
    analyses, rows = reviewed_pair()
    result = locate(model, {"S": TerminalInput(analyses["S"], "S")})
    assert not result.ok and result.diagnostics["model_domain"] == "unsupported" and not result.towers
    result = stage_e5(model, analyses["S"], analyses["R"], *(r["stages"]["intervals"][0] for r in rows))
    assert result["status"] == "withheld" and result["m"] is None


def test_user_corrected_corridor_identity_has_no_generated_patrol_towers():
    from pathlib import Path

    model = load_line(str(Path(__file__).parents[1] / "data/registry/dhn-nnr.yaml"))
    assert model.terminals["R"].substation == "NANSURALLA"
    assert model.model_review_required and not model.towers


def test_event_effective_settings_gaps_and_overlaps_do_not_fall_back_to_latest():
    old = RelaySetting(effective_from="2024-01-01", effective_to="2025-01-01")
    new = RelaySetting(effective_from="2026-01-01", effective_to="2027-01-01")
    relay = Relay("test", settings=[old, new])
    assert relay.setting_at("2024-06-01") is old
    assert relay.setting_at("2026-06-01") is new
    assert relay.setting_at("2025-06-01") is None
    assert relay.setting_at("2023-01-01") is None
    assert relay.setting_at("2028-01-01") is None
    relay.settings.append(RelaySetting(effective_from="2026-04-01"))
    assert relay.setting_at("2026-06-01") is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 101, True])
def test_invalid_patrol_chainage_never_enters_the_store(tmp_path, value):
    with Store(str(tmp_path / "truth.db")) as store:
        store.record_incident("A", "L", line_km=100, km_from_S=42)
        with pytest.raises(ValueError):
            store.confirm(Confirmation("A", chainage_km=value))
        assert store.latest_confirmation("A") is None


def test_orphan_and_not_found_truth_cannot_be_used_as_accepted_chainage(tmp_path):
    with Store(str(tmp_path / "truth.db")) as store:
        with pytest.raises(ValueError):
            store.confirm(Confirmation("absent", chainage_km=5))
        store.record_incident("A", "L", line_km=100, km_from_S=42)
        with pytest.raises(ValueError):
            store.confirm(Confirmation("A", chainage_km=42, cause="not found"))
        store.confirm(Confirmation("A", cause="not found"))
        assert store.accuracy()["scorable"] == 0


def test_unscorable_confirmations_cannot_open_tier2_gate(tmp_path):
    with Store(str(tmp_path / "truth.db")) as store:
        for i in range(100):
            identity = str(i)
            store.record_incident(identity, "L", line_km=100, km_from_S=42)
            store.confirm(Confirmation(identity, tower_no="unmapped tower"))
        out = store.accuracy()
        assert out["confirmations"] == 100 and out["tier2_eligible_events"] == 0 and not out["tier2_ready"]


def test_patrol_truth_cannot_be_silently_rebound_to_a_new_line(tmp_path):
    with Store(str(tmp_path / "truth.db")) as store:
        store.record_incident("A", "original", line_km=100, km_from_S=42)
        store.confirm(Confirmation("A", chainage_km=43))
        with pytest.raises(ValueError):
            store.record_incident("A", "different", line_km=200, km_from_S=5)
        assert store.incident("A")["line_id"] == "original"
        assert store.scored()[0].km_actual == 43
