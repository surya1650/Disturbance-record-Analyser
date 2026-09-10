"""Exact inspection bounds, source identity and read-only measurement semantics."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from dranalyser.application.worker import Worker
from dranalyser.comtrade.parser import read_comtrade
from dranalyser.workbench.samples import sample_interval
from tests import test_application as fixtures

environment = fixtures.environment


@pytest.fixture
def analysed(environment):
    client, app, source, registry = environment
    response = client.post(
        "/api/intake",
        files=fixtures.payload(source),
        data={
            "metadata": json.dumps(
                {"assignments": {"S/event.cfg": {"end": "S", "role": "primary"}}, "auto_analyse": True}
            )
        },
    )
    identity = response.json()["incident_id"]
    assert Worker(app.state.store, registry).once()
    row = client.get(f"/api/incidents/{identity}").json()
    assert row["state"] == "completed"
    return client, app, row


def test_native_values_inclusive_bounds_dc_rms_peak_and_revision_unchanged(analysed):
    client, app, row = analysed
    before = copy.deepcopy(app.state.store.get(row["incident_id"]))
    rec = read_comtrade(str(Path(row["bundle"]["root"]) / "S/event.cfg"))
    lo, hi = float(rec.t[100]), float(rec.t[109])
    out = sample_interval(app.state.store.root, row, "S/event.cfg", "IA", lo, hi)
    assert [p[0] for p in out["samples"]] == list(range(100, 110))
    np.testing.assert_array_equal([p[2] for p in out["samples"]], rec.analog["IA"][100:110])
    assert out["metrics"]["rms"] == pytest.approx(np.sqrt(np.mean(rec.analog["IA"][100:110] ** 2)))
    assert out["metrics"]["peak_abs"] == max(abs(rec.analog["IA"][100:110]))
    assert out["metrics"]["sample_count"] == 10
    assert out["source_id"] and out["unit"] == "A"
    assert app.state.store.get(row["incident_id"]) == before


@pytest.mark.parametrize("case", ["bounds", "nan", "reverse", "channel", "filename", "identity", "path", "tampered"])
def test_bad_bounds_identity_or_modified_sources_refuse(analysed, case):
    _, app, row = analysed
    lo, hi, filename, channel = 0.1, 0.2, "S/event.cfg", "IA"
    if case == "bounds":
        lo = -1
    if case == "nan":
        hi = float("nan")
    if case == "reverse":
        lo, hi = hi, lo
    if case == "channel":
        channel = "UNMAPPED"
    if case == "filename":
        filename = "../other/event.cfg"
    if case == "identity":
        entry = next(c for c in row["bundle"]["files"][0]["channel_inventory"] if c["selected"] == "IA")
        entry["id"] = "A999"
    if case == "path":
        row["bundle"]["root"] = str(app.state.store.root)
    if case == "tampered":
        dat = Path(row["bundle"]["root"]) / "S/event.dat"
        dat.write_bytes(dat.read_bytes().replace(b",", b",", 1) + b"\n")
    with pytest.raises(ValueError):
        sample_interval(app.state.store.root, row, filename, channel, lo, hi)


def test_sample_endpoint_requires_revision_and_does_not_rewrite_report(analysed):
    client, _, row = analysed
    identity = row["incident_id"]
    report = client.get(f"/api/incidents/{identity}/report?revision=1").content
    query = {"record": "S/event.cfg", "channel": "VA", "start_s": 0.1, "end_s": 0.12}
    url = f"/api/incidents/{identity}/samples"
    assert client.get(url, params=query).status_code == 422
    response = client.get(url, params={**query, "revision": 1})
    assert response.status_code == 200
    assert len(response.json()["samples"]) == 21
    assert client.get(url, params={**query, "revision": 999}).status_code == 404
    assert client.get(f"/api/incidents/{identity}/report?revision=1").content == report


def test_one_sample_and_empty_between_samples_are_honest(analysed):
    _, app, row = analysed
    one = sample_interval(app.state.store.root, row, "S/event.cfg", "IA", 0.1, 0.1)
    assert one["metrics"]["sample_count"] == 1
    assert one["metrics"]["rms"] == one["metrics"]["peak_abs"] == abs(one["samples"][0][2])
    empty = sample_interval(app.state.store.root, row, "S/event.cfg", "IA", 0.1001, 0.1002)
    assert empty["samples"] == [] and empty["metrics"]["status"] == "no samples"
    assert empty["metrics"]["rms"] is None


def test_native_cap_refuses_instead_of_thinning_and_nonfinite_metrics_are_unavailable(analysed, monkeypatch):
    from dranalyser.workbench import samples

    _, app, row = analysed
    rec = read_comtrade(str(Path(row["bundle"]["root"]) / "S/event.cfg"))
    monkeypatch.setattr(samples, "read_comtrade", lambda *a, **kw: rec)
    rec.analog["IA"][100] = np.nan
    out = sample_interval(app.state.store.root, row, "S/event.cfg", "IA", 0.1, 0.105)
    assert out["samples"][0][2] is None
    assert out["metrics"]["status"] == "non-finite samples" and out["metrics"]["rms"] is None
    monkeypatch.setattr(samples, "MAX_SAMPLES", 3)
    with pytest.raises(ValueError, match="narrow"):
        sample_interval(app.state.store.root, row, "S/event.cfg", "IA", 0.1, 0.105)
