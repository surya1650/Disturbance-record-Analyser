"""Unmapped analog inspection cannot change canonical samples or analysis."""

import json
from pathlib import Path

import numpy as np
import pytest

from dranalyser.application.worker import Worker
from dranalyser.comtrade.parser import read_cff, read_comtrade
from dranalyser.dsp.pipeline import analyse
from dranalyser.report.navigation import navigation_record
from dranalyser.rules.evidence import relay_evidence
from dranalyser.workbench.samples import sample_interval
from scripts.create_demo import create_demo
from tests import test_application as fixtures

environment, payload = fixtures.environment, fixtures.payload


def add_unmapped(cfg):
    lines = cfg.read_text().splitlines()
    total, acount, dcount = lines[1].split(",")
    na = int(acount[:-1])
    lines[1] = f"{int(total) + 1},{na + 1}A,{dcount}"
    lines.insert(2 + na, f"{na + 1},Rotor angle,,,deg,2,3,0,-32767,32767,110,1,S")
    cfg.write_text("\n".join(lines) + "\n")
    target = cfg.with_suffix(".dat")
    result = []
    for line in target.read_text().splitlines():
        values = line.split(",")
        values.insert(2 + na, "7")
        result.append(",".join(values))
    target.write_text("\n".join(result) + "\n")
    return f"A{na + 1}"


@pytest.mark.parametrize("format", ["cfg", "cff"])
def test_unmapped_values_use_declared_engineering_units_and_never_feed_dsp(tmp_path, format):
    cfg = create_demo(tmp_path / "synthetic") / "S/event.cfg"
    original = read_comtrade(str(cfg))
    source_id = add_unmapped(cfg)
    if format == "cff":
        target = cfg.with_suffix(".cff")
        target.write_bytes(
            b"--- file type: CFG ---\n"
            + cfg.read_bytes()
            + b"--- file type: DAT ASCII ---\n"
            + cfg.with_suffix(".dat").read_bytes()
        )
        rec = read_cff(str(target))
    else:
        rec = read_comtrade(str(cfg))
    assert source_id not in rec.analog
    assert rec.inspection_meta[source_id].unit == "deg"
    assert not rec.inspection_meta[source_id].normalised
    np.testing.assert_array_equal(rec.inspection_analog[source_id], 17)  # 7*2+3, not *110
    for name in original.analog:
        np.testing.assert_array_equal(rec.analog[name], original.analog[name])
    old, new = analyse(original), analyse(rec)
    assert old.fault_type == new.fault_type and old.window == new.window
    for key in old.ps.phasors:
        np.testing.assert_array_equal(old.ps.phasors[key], new.ps.phasors[key])
    nav = navigation_record(new, relay_evidence(new, "event"))
    channel = next(c for c in nav["analog"] if c["name"] == source_id)
    assert channel["unit"] == "deg" and "excluded from analysis" in channel["scaling"]
    assert channel["bins"][0][2:4] == [17, 17]


def test_revision_bound_native_source_samples_and_saved_navigation(environment):
    client, app, source, registry = environment
    source_id = add_unmapped(source / "S/event.cfg")
    uploaded = client.post(
        "/api/intake",
        files=payload(source),
        data={
            "metadata": json.dumps(
                {"assignments": {"S/event.cfg": {"end": "S", "role": "primary"}}, "auto_analyse": True}
            )
        },
    )
    identity = uploaded.json()["incident_id"]
    assert Worker(app.state.store, registry).once()
    row = app.state.store.get(identity)
    assert row["state"] == "completed", row
    before = client.get(f"/api/incidents/{identity}/report?revision=1").content
    data = sample_interval(app.state.store.root, row, "S/event.cfg", source_id, 0.1, 0.105)
    assert data["unit"] == "deg" and data["metrics"]["rms"] == 17
    assert data["metrics"]["peak_abs"] == 17 and all(s[2] == 17 for s in data["samples"])
    assert data["source_id"] == source_id and "no CT/VT" in data["scaling"]
    nav = client.get(f"/api/incidents/{identity}/navigator?revision=1").json()
    assert source_id in json.dumps(nav)
    assert client.get(f"/api/incidents/{identity}/report?revision=1").content == before
    rec = read_comtrade(str(Path(row["bundle"]["root"]) / "S/event.cfg"))
    mapped = next(c for c in rec.notes["channel_inventory"] if c["selected"] == "IA")
    with pytest.raises(ValueError):
        sample_interval(app.state.store.root, row, "S/event.cfg", mapped["id"], 0.1, 0.105)
