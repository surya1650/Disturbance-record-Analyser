"""Tests for ground-truth capture.

This is the table that makes the accuracy dashboard and the learning layer
possible, so the properties worth protecting are auditability and refusal to
guess, not throughput.
"""
from __future__ import annotations

import threading
import urllib.parse
import urllib.request

import pytest

from dranalyser.groundtruth import Confirmation, Store
from dranalyser.groundtruth.web import serve


def _store(tmp_path, n_incidents: int = 1) -> Store:
    s = Store(str(tmp_path / "gt.db"))
    for i in range(n_incidents):
        s.record_incident(
            "INC-" + str(i), "LINE-A", fault_time="2026-04-0%d 03:00:00" % (i + 1),
            fault_type="AG", m=0.30 + 0.01 * i, km_from_S=18.0 + i, line_km=62.0,
            method="E5", mode="two-ended", verdict="Correct operation")
    return s


def test_a_new_incident_starts_pending(tmp_path):
    s = _store(tmp_path, 3)
    assert len(s.pending()) == 3
    assert s.accuracy()["confirmations"] == 0
    assert s.accuracy()["tier2_ready"] is False


def test_re_running_the_analyser_updates_the_estimate_not_the_confirmation(tmp_path):
    s = _store(tmp_path)
    s.confirm(Confirmation(incident_id="INC-0", tower_no="52", chainage_km=18.4))
    s.record_incident("INC-0", "LINE-A", km_from_S=19.5, line_km=62.0,
                      mode="two-ended", method="E5")
    assert s.incident("INC-0")["km_from_S"] == pytest.approx(19.5)
    assert s.latest_confirmation("INC-0")["tower_no"] == "52"
    assert len(s.pending()) == 0


def test_a_correction_appends_and_never_overwrites(tmp_path):
    s = _store(tmp_path)
    s.confirm(Confirmation(incident_id="INC-0", tower_no="52", chainage_km=18.4,
                           confirmed_at="2026-04-10 09:00:00"))
    s.confirm(Confirmation(incident_id="INC-0", tower_no="53", chainage_km=18.8,
                           confirmed_at="2026-04-11 09:00:00"))
    rows = s._query("SELECT * FROM ground_truth WHERE incident_id = 'INC-0'")
    assert len(rows) == 2, "history must be auditable, not editable"
    assert s.latest_confirmation("INC-0")["tower_no"] == "53"
    assert s.scored()[0].km_actual == pytest.approx(18.8)


def test_an_empty_confirmation_is_refused(tmp_path):
    s = _store(tmp_path)
    with pytest.raises(ValueError):
        s.confirm(Confirmation(incident_id="INC-0"))
    # but "we looked and found nothing" is a legitimate, valuable result
    s.confirm(Confirmation(incident_id="INC-0", cause="not found"))
    assert s.latest_confirmation("INC-0")["cause"] == "not found"


def test_a_confirmation_without_a_chainage_is_stored_but_not_scored(tmp_path):
    """A tower number with no chainage still belongs in the table."""
    s = _store(tmp_path)
    s.confirm(Confirmation(incident_id="INC-0", tower_no="52"))
    assert s.accuracy()["confirmations"] == 1
    assert s.accuracy()["scorable"] == 0
    assert s.scored()[0].error_km is None


def test_error_is_signed_and_reported_as_a_fraction_of_the_line(tmp_path):
    s = _store(tmp_path)
    s.confirm(Confirmation(incident_id="INC-0", tower_no="52", chainage_km=18.4))
    sc = s.scored()[0]
    assert sc.error_km == pytest.approx(18.0 - 18.4)
    assert sc.error_pct == pytest.approx(100.0 * (18.0 - 18.4) / 62.0)


def test_accuracy_reports_the_tail_not_only_the_mean(tmp_path):
    """A locator with a good mean and a bad tail gets abandoned."""
    s = _store(tmp_path, 10)
    for i in range(10):
        actual = 18.0 + i + (5.0 if i == 9 else 0.02)
        s.confirm(Confirmation(incident_id="INC-" + str(i), tower_no=str(i),
                               chainage_km=actual))
    a = s.accuracy()
    assert a["scorable"] == 10
    assert a["mae_km"] < a["max_km"]
    assert a["p90_km"] >= a["mae_km"]
    assert a["max_km"] == pytest.approx(5.0, abs=0.01)
    assert "p90" in s.accuracy_report()


def test_tier2_gate_is_reported_and_not_reached_early(tmp_path):
    s = _store(tmp_path, 5)
    for i in range(5):
        s.confirm(Confirmation(incident_id="INC-" + str(i), tower_no=str(i),
                               chainage_km=18.0 + i))
    a = s.accuracy()
    assert a["tier2_gate"] == 100
    assert a["tier2_ready"] is False
    assert "stays gated off" in s.accuracy_report()


def test_store_is_usable_from_another_thread(tmp_path):
    """The capture form serves requests off the main thread."""
    s = _store(tmp_path)
    errs = []

    def work():
        try:
            s.confirm(Confirmation(incident_id="INC-0", tower_no="7", chainage_km=1.0))
            s.pending()
            s.accuracy_report()
        except Exception as exc:                       # noqa: BLE001
            errs.append(exc)

    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert not errs, errs


# --------------------------------------------------------------------------
def test_capture_form_serves_lists_and_records(tmp_path):
    s = _store(tmp_path, 2)
    httpd = serve(s, "127.0.0.1", 8237)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:8237"
    try:
        idx = urllib.request.urlopen(base + "/", timeout=5).read().decode()
        assert "INC-0" in idx and "INC-1" in idx
        assert "ACCURACY" in idx

        form = urllib.request.urlopen(base + "/confirm/INC-0", timeout=5).read().decode()
        assert "18.00 km" in form
        assert "Record what you actually found" in form

        data = urllib.parse.urlencode(
            {"tower_no": "52", "chainage_km": "18.4", "cause": "tree or vegetation",
             "confirmed_by": "patrol"}).encode()
        out = urllib.request.urlopen(base + "/confirm/INC-0", data=data,
                                     timeout=5).read().decode()
        assert "Recorded" in out
        assert s.latest_confirmation("INC-0")["tower_no"] == "52"

        unknown = urllib.request.urlopen(base + "/confirm/nope",
                                         timeout=5).read().decode()
        assert "Unknown incident" in unknown
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_capture_form_rejects_an_empty_submission_without_500(tmp_path):
    s = _store(tmp_path)
    httpd = serve(s, "127.0.0.1", 8238)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        out = urllib.request.urlopen("http://127.0.0.1:8238/confirm/INC-0",
                                     data=b"", timeout=5).read().decode()
        assert "Not recorded" in out
        assert s.latest_confirmation("INC-0") is None
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_capture_form_escapes_what_the_field_types_in(tmp_path):
    s = _store(tmp_path)
    s.confirm(Confirmation(incident_id="INC-0", tower_no="<script>x</script>",
                           chainage_km=1.0))
    httpd = serve(s, "127.0.0.1", 8239)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        form = urllib.request.urlopen("http://127.0.0.1:8239/confirm/INC-0",
                                      timeout=5).read().decode()
        assert "<script>x</script>" not in form
        assert "&lt;script&gt;" in form
    finally:
        httpd.shutdown()
        httpd.server_close()
