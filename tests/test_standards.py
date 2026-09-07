"""Source-grounded FOLD/APTRANSCO standards checks."""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pytest

from dranalyser.cli import build_parser
from dranalyser.registry.model import uniform_line
from dranalyser.registry.rio import RioSettings, RioZone, ZoneCharacteristic
from dranalyser.rules.signals import map_signals
from dranalyser.signals import AnalogMeta, Record
from dranalyser.standards import (audit_record, audit_settings,
                                  load_catalogue, load_encroachment_min_ohm,
                                  load_sources, search_chunks)


def _record(fs=1000.0, pre=0.5, post=2.5, complete=True):
    start = dt.datetime(2026, 1, 1)
    n = int(round((pre + post) * fs)) + 1
    t = np.arange(n) / fs
    channels = ("IA", "IB", "IC", "IN", "VA", "VB", "VC", "VN") if complete else \
        ("IA", "IB", "IC", "VA", "VB", "VC")
    analog = {name: np.zeros(n) for name in channels}
    meta = {name: AnalogMeta(name, "A" if name.startswith("I") else "V",
                             1.0, 0.0, 1.0, 1.0, "P", -32768, 32767)
            for name in channels}
    names = [
        "Relay PICKUP", "Dis.Gen. Trip", "Z1", "R PH OPEN", "A/R Start",
        "Dis.T.SEND L1", "VT Fuse Fail", "Main 2 Fail",
        "Time Synchronization Error", "LAN Network Error",
    ] if complete else []
    return Record(
        record_id="T", station="S", device_id="R", rev_year="2013",
        start_time=start, trigger_time=start + dt.timedelta(seconds=pre),
        fs=fs, line_freq=50.0, t=t, analog=analog,
        digital={name: np.zeros(n, dtype=bool) for name in names},
        analog_meta=meta,
    )


def _polygon(reach: complex, reverse=False):
    r, x = abs(reach.real), abs(reach.imag)
    if reverse:
        points = [(-r, -x), (r, -x), (r, 0.0), (-r, 0.0)]
    else:
        points = [(-r, 0.0), (r, 0.0), (r, x), (-r, x)]
    return ZoneCharacteristic("phase", points)


def test_record_that_meets_wg3_minima_passes_the_record_audit():
    result = audit_record(_record())
    assert result.status == "PASS"
    assert len(result.passes) == 5
    assert not result.gaps


def test_short_sparse_record_reports_specific_gaps():
    result = audit_record(_record(fs=800.0, pre=0.1, post=0.2, complete=False))
    ids = {c.id for c in result.gaps}
    assert ids == {"DR-SAMPLE", "DR-PRE", "DR-POST", "DR-ANALOG", "DR-DIGITAL"}
    assert "missing IN, VN" in next(c.actual for c in result.gaps if c.id == "DR-ANALOG")


def test_health_channels_have_canonical_mappings():
    mapped = map_signals(["Time Synchronization Error", "LAN Network Error",
                          "Main-2 Relay Fail", "CB Ready"])
    assert mapped.has("TIME_SYNC_FAIL")
    assert mapped.has("LAN_FAIL")
    assert mapped.has("RELAY_FAIL")
    assert mapped.has("CB_READY")


def test_load_encroachment_formula_reproduces_the_workbook_example():
    primary = load_encroachment_min_ohm(400.0, 874.0, 83.71)
    assert primary == pytest.approx(61.9241642310, rel=1e-10)
    assert primary / (400000 / 110 / 1000) == pytest.approx(17.029145, rel=2e-5)


def test_settings_audit_accepts_source_aligned_reach_and_timing():
    z1_per_km = complex(0.04, 0.40)
    line = uniform_line("T", "test", 220.0, 100.0, z1_per_km, complex(0.2, 1.2))
    line.terminals["S"].it.ct_ratio = 800.0
    line.terminals["S"].it.vt_ratio = 2000.0
    angle = math.degrees(math.atan2(line.z1.imag, line.z1.real))
    scale = line.terminals["S"].it.vt_ratio / line.terminals["S"].it.ct_ratio
    z1_secondary = 0.8 * line.z1 / scale
    settings = RioSettings(
        line_angle_deg=angle, re_rl=1.02, xe_xl=0.8,
        zones=[
            RioZone("Z1", t1=0.0, phase=_polygon(z1_secondary)),
            RioZone("Z2", t1=0.35, phase=_polygon(1.2 * line.z1 / scale)),
            RioZone("Z3", t1=0.70, phase=_polygon(1.5 * line.z1 / scale)),
            RioZone("Z5", t1=0.35, phase=_polygon(0.2 * line.z1 / scale, reverse=True)),
        ],
    )
    result = audit_settings(settings, line)
    assert not result.gaps
    assert {c.id for c in result.passes} >= {
        "SET-Z1", "SET-Z2-TIME", "SET-Z3-TIME", "SET-REVERSE", "SET-K0"
    }
    assert any(c.id == "SET-RLD" for c in result.not_evaluable)


def test_standards_subcommand_is_registered():
    args = build_parser().parse_args(["standards", "record.cfg", "--end", "R"])
    assert args.cmd == "standards" and args.end == "R"


def test_source_manifest_and_catalogue_cover_the_complete_pack():
    sources = load_sources()
    chunks = load_catalogue()
    source_ids = {item["id"] for item in sources}
    assert len(sources) == 4
    assert all(len(item["sha256"]) == 64 for item in sources)
    assert len(chunks) >= 35
    assert len({item["id"] for item in chunks}) == len(chunks)
    assert {item["source_id"] for item in chunks} == source_ids
    assert all(item["rules"] for item in chunks)
    assert all(item["locator"] for item in chunks)


@pytest.mark.parametrize("asset", [
    "line", "transformer", "reactor", "busbar", "generator", "renewable",
])
def test_catalogue_is_searchable_for_every_documented_asset_class(asset):
    assert search_chunks(asset_type=asset)


def test_catalogue_can_filter_active_load_encroachment_context():
    chunks = search_chunks(asset_type="line", topic="load-encroachment",
                           active_only=True)
    assert {item["source_id"] for item in chunks} == {
        "aptransco-general-philosophy",
        "aptransco-distance-review-2024",
        "load-encroachment-workbook",
    }


def test_standards_context_mode_does_not_require_a_record(capsys):
    args = build_parser().parse_args([
        "standards", "--show-context", "--asset-type", "busbar",
    ])
    assert args.func(args) == 0
    assert "WG3-BUSBAR" in capsys.readouterr().out
