"""Display-data oracles and revision isolation; these are not TB 854 validation."""

import copy
import datetime as dt
import json

import numpy as np
import pytest

from dranalyser.application.worker import Worker
from dranalyser.dsp.pipeline import analyse
from dranalyser.report.navigation import envelope, navigation_record, phase_loops
from dranalyser.rules.evidence import relay_evidence
from dranalyser.signals import AnalogMeta
from tests import test_application as fixtures
from tests.test_evidence_application import pair_payload
from tests.test_operation_compare import waveform

environment = fixtures.environment


def analysed_wave():
    rec = waveform(1000, 0.12, 0)
    for key in rec.analog:
        rec.analog_meta[key] = AnalogMeta(
            key, "A" if key.startswith("I") else "V", 1, 0, 1, 1, "P", -1e6, 1e6, normalised=True
        )
    return analyse(rec)


def test_envelope_keeps_impulse_extrema_missing_bins_and_time_support():
    t = np.arange(10000) / 1000
    values = np.zeros(10000)
    values[201] = 999
    values[209] = -345
    values[601] = np.nan
    bins = envelope(t, values, limit=100)
    assert len(bins) == 100 and sum(b[4] for b in bins) == 10000
    assert bins[2] == [0.2, 0.299, -345, 999, 100]
    assert bins[6] == [0.6, 0.699, None, None, 100]
    assert bins[0][0] == t[0] and bins[-1][1] == t[-1]
    json.dumps(bins, allow_nan=False)


def test_single_sample_bins_are_original_values_and_bad_length_is_unavailable():
    assert envelope(np.array([0.1, 0.2]), np.array([-2, 3])) == [[0.1, 0.1, -2, -2, 1], [0.2, 0.2, 3, 3, 1]]
    assert envelope(np.arange(3), np.arange(2)) == []


def test_phase_loop_plot_matches_independent_sinusoidal_impedance_and_keeps_invalid_dft_prefix():
    an = analysed_wave()
    rec = an.record
    # Independent balanced sine circuit: 13-ohm magnitude and atan2(12,5) phase lead.
    theta = np.arctan2(12, 5)
    for p, angle in zip("ABC", [0, -2 * np.pi / 3, 2 * np.pi / 3], strict=True):
        rec.analog["I" + p] = 10 * np.sqrt(2) * np.cos(2 * np.pi * 50 * rec.t + angle)
        rec.analog["V" + p] = 130 * np.sqrt(2) * np.cos(2 * np.pi * 50 * rec.t + angle + theta)
    an = analyse(rec)
    out = phase_loops(an)
    assert set(out["loops"]) == {"AB", "BC", "CA"}
    for rows in out["loops"].values():
        assert all(p[1] is None for p in rows[: an.ps.n_window])
        values = np.array([p[1:] for p in rows if p[1] is not None])
        assert values[:, 0] == pytest.approx(5, abs=1e-7)
        assert values[:, 1] == pytest.approx(12, abs=1e-7)


@pytest.mark.parametrize("problem", ["scaling", "missing", "multirate", "gap"])
def test_unsupported_rx_prerequisites_are_explicit(problem):
    an = analysed_wave()
    if problem == "scaling":
        an.record.analog_meta["IA"].normalised = False
    if problem == "missing":
        del an.ps.phasors["VB"]
    if problem == "multirate":
        an.record.nrates = 2
    if problem == "gap":
        an.record.t[200:] += 0.05
    out = phase_loops(an)
    assert not out["loops"] and out["reason"]


def test_zero_current_and_nonfinite_bins_never_join_a_trajectory_across_a_gap():
    an = analysed_wave()
    for p in "ABC":
        an.ps.phasors["I" + p][120:145] = 0j
    out = phase_loops(an, limit=40)
    assert all(p[1] is None for p in out["loops"]["AB"] if 0.12 <= p[0] < 0.15)
    json.dumps(out, allow_nan=False)


def test_digital_initial_terminal_boundaries_and_unknown_trigger_survive_navigation():
    an = analysed_wave()
    an.record.trigger_time = None
    an.record.digital = {"CB Open A": np.ones(an.record.n), "Unmapped point": np.zeros(an.record.n)}
    evidence = relay_evidence(an, "S/Main-2/event.cfg", "S", "corroborating", protection_system="Main-2")
    out = navigation_record(an, evidence)
    point = out["digital"][0]
    assert point["intervals"][0]["onset_unknown"] and point["intervals"][0]["continues_at_capture_end"]
    assert point["intervals"][0]["start_ms"] is None
    assert out["digital"][1]["meanings"] == []
    assert out["capture_s"] == [0, 0.399]
    assert evidence["trigger_offset_s"] is None


def test_normalized_voltage_plot_uses_volts_even_when_cfg_declares_kilovolts():
    an = analysed_wave()
    an.record.analog_meta["VA"].unit = "kV"
    out = navigation_record(an, relay_evidence(an, "a.cfg"))
    voltage = next(c for c in out["analog"] if c["name"] == "VA")
    assert voltage["unit"] == "V" and voltage["declared_unit"] == "kV"
    assert voltage["bins"][5][2] == an.record.analog["VA"][5]


def test_display_does_not_change_analysis_or_apply_other_clock_offsets():
    an = analysed_wave()
    before = copy.deepcopy(an)
    evidence = relay_evidence(an, "S/event.cfg", "S")
    out = navigation_record(an, evidence)
    an.record.start_time += dt.timedelta(seconds=1418)
    an.record.trigger_time += dt.timedelta(seconds=1418)
    other = navigation_record(an, relay_evidence(an, "S/event.cfg", "S"))
    assert out == other
    assert an.window == before.window
    for key in an.ps.phasors:
        np.testing.assert_equal(an.ps.phasors[key], before.ps.phasors[key])


@pytest.mark.parametrize("problem", ["multirate", "gap", "nonmonotonic"])
def test_untrustworthy_time_continuity_never_produces_continuous_digital_state(problem):
    an = analysed_wave()
    if problem == "multirate":
        an.record.nrates = 2
    if problem == "gap":
        an.record.t[100:] += 0.1
    if problem == "nonmonotonic":
        an.record.t[100] = an.record.t[99]
    out = navigation_record(an, relay_evidence(an, "a.cfg"))
    if problem == "nonmonotonic":
        assert out["status"] == "unavailable"
    else:
        assert all(not p["intervals"] and p["state"] == "unavailable for continuous navigation" for p in out["digital"])


def test_revision_navigator_is_frozen_and_endpoint_refuses_paths_outside_run_root(environment):
    client, app, source, registry = environment
    assignment = {"S/Main-1/event.cfg": {"end": "S", "role": "primary", "protection_system": "Main-1"}}
    response = client.post(
        "/api/intake",
        files=pair_payload(source, "S", "Main-1"),
        data={"metadata": json.dumps({"assignments": assignment, "auto_analyse": True})},
    )
    identity = response.json()["incident_id"]
    worker = Worker(app.state.store, registry)
    assert worker.once()
    url = f"/api/incidents/{identity}/navigator?revision=1"
    saved = client.get(url)
    assert saved.status_code == 200
    assert saved.json()["records"][0]["status"] == "available"
    assert client.get(f"/api/incidents/{identity}/navigator").status_code == 422
    assert client.get(f"/api/incidents/{identity}/navigator?revision=99").status_code == 404
    assert client.post(f"/api/incidents/{identity}/reanalyse?revision=1").status_code == 202
    assert worker.once()
    assert client.get(f"/api/incidents/{identity}/navigator?revision=2").status_code == 404
    assert (
        client.post(f"/api/incidents/{identity}/review", json={"revision": 2, "assignments": assignment}).status_code
        == 202
    )
    assert worker.once()
    assert client.get(url).content == saved.content
    with app.state.store.connect() as db:
        db.execute(
            "UPDATE revisions SET result=? WHERE incident_id=? AND number=2",
            (json.dumps({"navigator_path": str(source)}), identity),
        )
    assert client.get(f"/api/incidents/{identity}/navigator?revision=2").status_code == 404
