"""Reviewed identities are exact-record declarations, never sample/scaling repairs."""

import copy

import numpy as np
import pytest

from dranalyser.application.worker import Worker
from dranalyser.comtrade.conformance import check
from dranalyser.comtrade.parser import read_cff, read_comtrade
from dranalyser.dsp.pipeline import _find_trip, analyse
from dranalyser.rules.evidence import relay_evidence
from dranalyser.rules.signals import map_signals
from dranalyser.standards.recording import recording_points
from dranalyser.workbench.channel_mapping import clean_mapping
from scripts.create_demo import create_demo
from tests import test_application as fixtures

environment = fixtures.environment


@pytest.fixture
def original(tmp_path):
    cfg = create_demo(tmp_path / "original") / "S/event.cfg"
    return cfg, read_comtrade(str(cfg))


def mapping(rec, analog=None, digital=None):
    return {
        "record_hash": rec.content_hash,
        "reason": "Reviewed synthetic channel schedule",
        "analog": analog or {},
        "digital": digital or {},
    }


def source_id(rec, target):
    return next(c["id"] for c in rec.notes["channel_inventory"] if c["kind"] == "analog" and c["selected"] == target)


def rename(cfg, position, text):
    lines = cfg.read_text().splitlines()
    parts = lines[position + 1].split(",")
    parts[1] = text
    lines[position + 1] = ",".join(parts)
    cfg.write_text("\n".join(lines) + "\n")


@pytest.mark.parametrize("format", ["cfg", "cff"])
def test_unmapped_current_recovered_before_gating_with_original_values_and_hash(format, original):
    cfg, baseline = original
    key = source_id(baseline, "IA")
    rename(cfg, int(key[1:]), "Unknown input")
    reader, source = read_comtrade, cfg
    if format == "cff":
        source = cfg.with_suffix(".cff")
        source.write_bytes(
            b"--- file type: CFG ---\n"
            + cfg.read_bytes()
            + b"--- file type: DAT ASCII ---\n"
            + cfg.with_suffix(".dat").read_bytes()
        )
        reader = read_cff
    auto = reader(str(source))
    check(auto)
    assert auto.blocked() and "IA" not in auto.analog
    original_bytes = source.read_bytes()
    reviewed = reader(str(source), channel_mapping=mapping(auto, {key: "IA"}))
    check(reviewed)
    assert not reviewed.blocked()
    np.testing.assert_array_equal(reviewed.analog["IA"], baseline.analog["IA"])
    np.testing.assert_array_equal(reviewed.raw_analog["IA"], baseline.raw_analog["IA"])
    assert reviewed.content_hash == auto.content_hash
    assert reviewed.analog_meta["IA"].raw_id == "Unknown input"
    assert source.read_bytes() == original_bytes
    assert any(f.code == "CH-REVIEW" for f in reviewed.flags)


def test_phase_swap_is_explicit_and_preserves_ratios_and_samples(original):
    cfg, before = original
    ia, ib = source_id(before, "IA"), source_id(before, "IB")
    after = read_comtrade(str(cfg), channel_mapping=mapping(before, {ia: "IB", ib: "IA"}))
    np.testing.assert_equal(after.analog["IA"], before.analog["IB"])
    assert after.analog_meta["IA"].primary == before.analog_meta["IB"].primary
    assert after.analog_meta["IA"].ps == before.analog_meta["IB"].ps
    assert after.notes["channel_mapping"]["analog"] == {ia: "IB", ib: "IA"}


@pytest.mark.parametrize("problem", ["hash", "collision", "quantity", "absent"])
def test_wrong_hash_colliding_quantity_or_absent_position_refuses_mapping(problem, original):
    cfg, rec = original
    key = source_id(rec, "IA")
    declaration = mapping(rec, {key: "IA"})
    if problem == "hash":
        declaration["record_hash"] = "0" * 64
    if problem == "collision":
        declaration["analog"][key] = "IB"
    if problem == "quantity":
        declaration["analog"][key] = "VA"
    if problem == "absent":
        declaration["analog"] = {"A999": "IA"}
    with pytest.raises(ValueError):
        read_comtrade(str(cfg), channel_mapping=declaration)


def test_ignore_is_not_a_conformance_bypass_and_truncation_stays_blocked(original):
    cfg, rec = original
    missing = read_comtrade(str(cfg), channel_mapping=mapping(rec, {source_id(rec, "IA"): "ignore"}))
    check(missing)
    assert missing.blocked()
    dat = cfg.with_suffix(".dat")
    dat.write_text("\n".join(dat.read_text().splitlines()[:-5]) + "\n")
    truncated = read_comtrade(str(cfg))
    reviewed = read_comtrade(str(cfg), channel_mapping=mapping(truncated, {source_id(rec, "IA"): "IA"}))
    check(reviewed)
    assert any(f.code == "CFG-TRUNC" and f.severity == "block" for f in reviewed.flags)


def test_digital_review_controls_evidence_dsp_and_audit_without_renaming_raw_point(original):
    cfg, rec = original
    entry = next(c for c in rec.notes["channel_inventory"] if c["kind"] == "digital" and "TRIP" in c["label"].upper())
    rename(cfg, len(rec.analog) + int(entry["id"][1:]), "Unidentified binary")
    auto = read_comtrade(str(cfg))
    reviewed = read_comtrade(str(cfg), channel_mapping=mapping(auto, digital={entry["id"]: "TRIP_A"}))
    assert "Unidentified binary" in reviewed.digital
    expected = auto.first_assert("Unidentified binary")
    assert _find_trip(reviewed) == expected
    evidence = relay_evidence(analyse(reviewed))
    point = next(s for s in evidence["signals"] if s["signal"] == "TRIP_A")
    assert point["points"][0]["channel"] == "Unidentified binary"
    assert recording_points(reviewed, "wg3-220plus-distance")["points"][0]["status"] == "pass"
    ignored = read_comtrade(str(cfg), channel_mapping=mapping(auto, digital={entry["id"]: "ignore"}))
    assert not map_signals(list(ignored.digital), ignored.notes["digital_overrides"]).has("TRIP_A")
    np.testing.assert_equal(reviewed.digital["Unidentified binary"], ignored.digital["Unidentified binary"])


def test_explicit_ignore_beats_exact_standard_label_and_automatic_trip(original):
    cfg, rec = original
    entry = next(c for c in rec.notes["channel_inventory"] if c["kind"] == "digital" and "TRIP" in c["label"].upper())
    rename(cfg, len(rec.analog) + int(entry["id"][1:]), "Trip R phase")
    auto = read_comtrade(str(cfg))
    reviewed = read_comtrade(str(cfg), channel_mapping=mapping(auto, digital={entry["id"]: "ignore"}))
    assert recording_points(reviewed, "wg3-220plus-distance")["points"][0]["status"] == "gap"
    assert "Trip R phase" in map_signals(list(reviewed.digital), reviewed.notes["digital_overrides"]).ignored


def test_duplicate_digital_labels_are_distinct_original_positions(original):
    cfg, rec = original
    entries = [c for c in rec.notes["channel_inventory"] if c["kind"] == "digital"]
    assert len(entries) >= 2
    for c in entries[:2]:
        rename(cfg, len(rec.analog) + int(c["id"][1:]), "Same label")
    auto = read_comtrade(str(cfg))
    assert len(auto.digital) == len(entries)
    duplicate = [c for c in auto.notes["channel_inventory"] if c["label"] == "Same label"]
    assert duplicate[0]["key"] != duplicate[1]["key"]
    after = read_comtrade(str(cfg), channel_mapping=mapping(auto, digital={duplicate[1]["id"]: "CARRIER_RECV"}))
    candidates = map_signals(list(after.digital), after.notes["digital_overrides"]).channels("CARRIER_RECV")
    assert candidates[0] == duplicate[1]['key']
    assert duplicate[0]['key'] not in candidates
    assert 'CARRIER_RECV' in candidates  # other existing evidence is not silently discarded


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.update(reason=""),
        lambda m: m.update(polarity=-1),
        lambda m: m["analog"].update(D1="IA"),
        lambda m: m["digital"].update(D1="BREAKER_VERIFIED_OPEN"),
    ],
)
def test_contract_requires_reason_and_supported_position_meaning(change):
    raw = {"record_hash": "a" * 64, "reason": "checked", "analog": {}, "digital": {}}
    change(raw)
    with pytest.raises(ValueError):
        clean_mapping(raw)


def test_application_review_reversal_and_revisions_keep_original_sources(environment):
    client, app, source, registry = environment
    files = fixtures.payload(source)
    response = client.post("/api/intake", files=files)
    identity = response.json()["incident_id"]
    worker = Worker(app.state.store, registry)
    assert worker.once()
    row = client.get(f"/api/incidents/{identity}").json()
    f = row["bundle"]["files"][0]
    key = next(c["id"] for c in f["channel_inventory"] if c["kind"] == "digital" and "TRIP" in c["label"].upper())
    declaration = {
        "record_hash": f["content_hash"],
        "reason": "Reviewed phase-specific synthetic trip",
        "analog": {},
        "digital": {key: "TRIP_A"},
    }
    assignment = {
        "S/event.cfg": {"end": "S", "role": "primary", "protection_system": "Main-1", "channel_mapping": declaration}
    }
    response = client.post(f"/api/incidents/{identity}/review", json={"revision": 1, "assignments": assignment})
    assert response.status_code == 202, response.text
    assert worker.once()
    one = client.get(f"/api/incidents/{identity}").json()
    assert one["state"] == "completed", one.get("error")
    assert one["result"]["relay_evidence"][0]["channel_mapping"] == declaration
    first = client.get(f"/api/incidents/{identity}/report?revision=1").content
    assert b"Reviewed channel mapping applied" in first
    assert client.post(f"/api/incidents/{identity}/reanalyse?revision=1").status_code == 202
    assert worker.once()
    restored = copy.deepcopy(assignment)
    del restored["S/event.cfg"]["channel_mapping"]
    assert (
        client.post(f"/api/incidents/{identity}/review", json={"revision": 2, "assignments": restored}).status_code
        == 202
    )
    assert worker.once()
    two = client.get(f"/api/incidents/{identity}").json()
    assert two["state"] == "completed" and not two["result"]["relay_evidence"][0]["channel_mapping"]
    assert two["files"] == one["files"]
    assert client.get(f"/api/incidents/{identity}/report?revision=1").content == first
    assert client.post(f"/api/incidents/{identity}/reanalyse?revision=2").status_code == 202
    assert worker.once()
    declaration["record_hash"] = "0" * 64
    response = client.post(f"/api/incidents/{identity}/review", json={"revision": 3, "assignments": assignment})
    assert response.status_code == 400
    assert client.get(f"/api/incidents/{identity}").json()["state"] == "needs_review"
