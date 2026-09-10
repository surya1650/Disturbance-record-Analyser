"""Independent waveform/edge fixtures for per-record operational evidence."""
import datetime as dt
import math
from types import SimpleNamespace

import numpy as np
import pytest

from dranalyser.dsp.measurements import phase_measurements, trigger_reference
from dranalyser.report.evidence import render_evidence
from dranalyser.rules.evidence import point_observation, relay_evidence, terminal_evidence
from dranalyser.signals import AnalogMeta, Record


def analysed(x=None, trigger=0.04, digital=None):
    t = np.arange(200)/1000
    if x is None:
        x = 10*np.sin(2*np.pi*50*t)
    start = dt.datetime(2026, 1, 1)
    rec = Record("fixture", "Station", "Relay", "2013", start,
                 start+dt.timedelta(seconds=trigger) if trigger is not None else None,
                 1000, 50, t, {"IA": np.array(x), "VA": 2*np.array(x)}, digital or {},
                 analog_meta={"IA": AnalogMeta("Original R current", "A", 1, 0, 800, 1, "S", -32768, 32767)})
    return SimpleNamespace(record=rec, window=SimpleNamespace(t_start=.02, t_end=.1, mode="full"),
                           inception=SimpleNamespace(t_refined=.02),
                           ps=SimpleNamespace(phasors={"IA": np.full(200, 10/math.sqrt(2)+0j)}),
                           indices=lambda: np.arange(40, 100), fault_type="AG", saturation=SimpleNamespace(detected=False),
                           clipping=[])


@pytest.mark.parametrize("dc,harmonic", [(0, 0), (3, 0), (0, 4), (3, 4)])
def test_rms_includes_dc_and_harmonics_without_peak_conversion(dc, harmonic):
    t = np.arange(200)/1000
    x = 10*np.sin(2*np.pi*50*t) + dc + harmonic*np.sin(2*np.pi*150*t)
    x[150] = 1e6  # outside the fault window; must not pollute either metric
    out = phase_measurements(analysed(x))
    row = out["channels"][0]
    assert row["rms"] == pytest.approx(math.sqrt(50+dc**2+harmonic**2/2), abs=1e-10)
    assert row["fundamental_rms"] == pytest.approx(10/math.sqrt(2))
    assert row["peak_abs"] < 20
    assert out["window"]["sample_count"] == 80
    assert out["window"]["start_trigger_ms"] == pytest.approx(-20)
    assert row["source_channel"] == "Original R current" and row["declared_ps"] == "S"
    assert row["unit"] == "A primary" and row["primary_ratio"] == 800
    if dc:
        assert abs(row["rms"]-row["peak_abs"]/math.sqrt(2)) > 0.5


def test_clipped_peak_is_reported_as_measured_and_missing_phases_stay_missing():
    an = analysed(np.tile([3., -3.], 100))
    an.clipping = ["IA"]
    out = relay_evidence(an)
    assert out["measurements"]["channels"][0]["rms"] == 3
    assert out["measurements"]["channels"][0]["peak_abs"] == 3
    assert out["measurements"]["channels"][1]["rms"] is None
    assert out["measurements"]["channels"][1]["status"] == "not recorded"
    assert out["clipped_channels"] == ["IA"]


@pytest.mark.parametrize("bad", ["one sample", "no inception", "nonfinite", "empty window"])
def test_invalid_windows_do_not_fall_back_to_whole_record_measurements(bad):
    an = analysed()
    if bad == "one sample":
        an.window.t_end = .021
    elif bad == "no inception":
        an.inception = None
    elif bad == "nonfinite":
        an.record.analog["IA"][30] = np.nan
    else:
        an.window.mode = "none"
    row = phase_measurements(an)["channels"][0]
    assert row["rms"] is None and row["peak_abs"] is None
    assert row["status"] != "measured"


@pytest.mark.parametrize("kind,expected", [("missing", "not recorded / unmapped"),
    ("low", "no assertion observed"), ("high", "active at capture start"), ("edge", "assertion observed")])
def test_operation_distinguishes_missing_inactive_initially_active_and_edges(kind, expected):
    x = np.zeros(200, dtype=bool)
    if kind == "high":
        x[:] = True
    elif kind == "edge":
        x[60:100] = True
    out = relay_evidence(analysed(digital={} if kind == "missing" else {"Any Trip": x}))
    assert out["trip_state"] == expected
    assert out["operate_ms"] == (pytest.approx(40) if kind == "edge" else None)
    if kind == "high":
        point = next(s for s in out["signals"] if s["signal"] == "TRIP")["points"][0]
        assert point["assertions_ms"] == []
        assert point["intervals"][0]["onset_unknown"]
        assert point["intervals"][0]["continues_at_capture_end"]


def test_trigger_zero_is_separate_from_detected_inception_and_operate_duration():
    digital = {"Any Trip": np.arange(200) >= 60}
    first = relay_evidence(analysed(trigger=.04, digital=digital))
    second = relay_evidence(analysed(trigger=.05, digital=digital))
    assert first["inception_trigger_ms"] == pytest.approx(-20)
    assert second["inception_trigger_ms"] == pytest.approx(-30)
    assert first["operate_ms"] == second["operate_ms"] == pytest.approx(40)
    p1 = next(s for s in first["signals"] if s["signal"] == "TRIP")["points"][0]
    p2 = next(s for s in second["signals"] if s["signal"] == "TRIP")["points"][0]
    assert p1["assertions_ms"] == pytest.approx([20])
    assert p2["assertions_ms"] == pytest.approx([10])


@pytest.mark.parametrize("trigger", [None, -1, 5])
def test_unavailable_trigger_never_becomes_an_invented_zero(trigger):
    an = analysed(trigger=trigger, digital={"Any Trip": np.arange(200) >= 60})
    assert trigger_reference(an.record)[0] is None
    out = relay_evidence(an)
    assert out["inception_trigger_ms"] is None
    assert out["measurements"]["channels"][0]["peak_trigger_ms"] is None
    assert out["operate_ms"] == pytest.approx(40)  # local duration needs no timestamp


def test_conflicting_raw_trip_candidates_remain_visible_without_arbitrary_winner():
    out = relay_evidence(analysed(digital={"Any Trip": np.arange(200) >= 60,
                                          "General Trip": np.zeros(200, bool)}))
    assert out["trip_state"] == "mapping review required"
    assert out["operate_ms"] is None
    trip = next(s for s in out["signals"] if s["signal"] == "TRIP")
    assert len(trip["points"]) == 2


def test_short_or_invalid_digital_stream_is_not_a_nonoperation():
    an = analysed(digital={"Any Trip": [False]})
    assert point_observation(an.record, "Any Trip", .04)["state"] == "insufficient samples"


def test_record_order_or_primary_role_does_not_erase_other_relay_evidence():
    a = relay_evidence(analysed(digital={"Any Trip": np.arange(200) >= 60}), "first", "S", "primary")
    b = relay_evidence(analysed(digital={"Any Trip": np.zeros(200, bool)}), "second", "S", "corroborating")
    forward, reverse = terminal_evidence([a, b]), terminal_evidence([b, a])
    assert forward == reverse
    assert "differ" in forward[0]["summary"]
    assert forward[1]["summary"] == "record unavailable; operation unknown"
    assert a["protection_system"] == b["protection_system"] == "unknown"


def test_export_escapes_original_names_and_contains_initial_and_open_intervals():
    out = relay_evidence(analysed(digital={"Any Trip <script>alert(1)</script>": np.ones(200, bool)}),
                         file_name="<img src=x onerror=alert(1)>")
    html = render_evidence([out], ["<script>bad</script>"])
    assert "<script>" not in html and "<img " not in html
    assert "&lt;script&gt;" in html and "onset unknown" in html
    assert "≤" in html and "≥" in html and "0 ms" in html
