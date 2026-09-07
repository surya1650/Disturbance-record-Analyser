"""Tests for the zone-decision back-test."""
from __future__ import annotations

import os

import pytest

from dranalyser import backtest
from dranalyser.backtest import Outcome
from dranalyser.registry.loader import load_line

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = [os.path.join(ROOT, "DR & Events 9-4-2026"), os.path.join(ROOT, "DR 9-4-2026")]
LINE = os.path.join(ROOT, "data", "registry", "dhn-nnr.yaml")
have = all(os.path.isdir(p) for p in CORPUS)
needs_corpus = pytest.mark.skipif(not have, reason="DHONE corpus not present")


def test_zone_agreement_treats_an_unresolvable_fast_trip_correctly():
    """Z1_OR_AIDED is not collapsed into Z1, but it agrees with a computed Z1."""
    o = Outcome(path="x", zone_operated="Z1_OR_AIDED", zone_expected="Z1")
    assert o.zone_comparable and o.zone_agrees is True
    o = Outcome(path="x", zone_operated="Z1_OR_AIDED", zone_expected="Z2")
    assert o.zone_agrees is False
    o = Outcome(path="x", zone_operated="Z2", zone_expected="Z2")
    assert o.zone_agrees is True


def test_a_record_without_settings_is_not_counted_as_agreement():
    """No settings means no computed zone, which is not a pass."""
    o = Outcome(path="x", zone_operated="Z2", zone_expected=None)
    assert not o.zone_comparable
    assert o.zone_agrees is None
    o = Outcome(path="x", zone_operated="Z2", zone_expected="beyond_all_zones")
    assert o.zone_agrees is None


def test_discover_finds_records_and_ignores_everything_else(tmp_path):
    (tmp_path / "a.CFG").write_text("x")
    (tmp_path / "b.cff").write_text("x")
    (tmp_path / "c.DAT").write_text("x")
    (tmp_path / "d.rio").write_text("x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "e.cfg").write_text("x")
    found = [os.path.basename(p) for p in backtest.discover([str(tmp_path)])]
    assert sorted(found) == ["a.CFG", "b.cff", "e.cfg"]


def test_a_broken_record_is_reported_not_skipped(tmp_path):
    bad = tmp_path / "broken.cfg"
    bad.write_text("this is not a comtrade file\n")
    res = backtest.run([str(tmp_path)])
    assert len(res.outcomes) == 1
    assert not res.outcomes[0].ok
    assert res.outcomes[0].error
    assert "FAILED" in res.report()


@needs_corpus
def test_backtest_over_the_real_corpus():
    res = backtest.run(CORPUS, line=load_line(LINE))
    assert len(res.outcomes) == 4
    assert all(o.ok for o in res.outcomes)
    # the two byte-identical records are collapsed by content hash
    assert len(res.duplicates) == 1


@needs_corpus
def test_every_zone_decision_in_the_corpus_agrees():
    """The relays' own trip decisions are the ground truth here."""
    res = backtest.run(CORPUS, line=load_line(LINE))
    good, judged = res.agreement()
    assert judged >= 2
    assert good == judged, [
        (o.record_id, o.zone_operated, o.zone_expected) for o in res.faults
        if o.zone_agrees is False]


@needs_corpus
def test_a_record_with_no_fault_is_analysed_and_not_called_a_fault():
    res = backtest.run(CORPUS, line=load_line(LINE))
    quiet = [o for o in res.analysed if not o.has_fault]
    assert quiet, "the 13-02-2026 record carries no fault current"
    for o in quiet:
        assert o.zone_operated is None or o.zone_agrees is None
    # and its spurious fault type is not advertised in the table
    assert res.report().count(" AB ") == 0


@needs_corpus
def test_report_ranks_the_recording_gaps():
    """The rules that cannot be judged are the work list for the fleet."""
    res = backtest.run(CORPUS, line=load_line(LINE))
    skipped = res.skipped_counts()
    assert skipped.get("CR-01", 0) >= 2
    assert "RULES THAT COULD NOT BE JUDGED" in res.report()


@needs_corpus
def test_csv_export_round_trips(tmp_path):
    import csv

    res = backtest.run(CORPUS, line=load_line(LINE))
    out = tmp_path / "bt.csv"
    res.to_csv(str(out))
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == len(res.outcomes)
    assert {"record_id", "zone_operated", "zone_expected", "verdict"} <= set(rows[0])
