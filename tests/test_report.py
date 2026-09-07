"""Tests for the two-page incident report."""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

import pytest

from dranalyser.comtrade.conformance import check
from dranalyser.comtrade.parser import read_comtrade
from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc.ensemble import TerminalInput, locate
from dranalyser.registry.loader import load_line
from dranalyser.registry.model import uniform_line
from dranalyser.registry.settings_io import load_settings
from dranalyser.report import build, render, write
from dranalyser.report.graphics import oscillogram, phasor_diagram, rx_diagram
from dranalyser.report.render import incident_id
from dranalyser.rules.engine import apply_rules, load_rules
from dranalyser.rules.features import incident_features
from dranalyser.synth.generator import SynthSpec, TerminalSpec, generate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M2 = os.path.join(ROOT, "DR & Events 9-4-2026", "Main-2", "DR-1", "DR-1.CFG")
RIO = os.path.join(ROOT, "DR & Events 9-4-2026", "Main-2", "DR-1", "DR-1.rio")
LINE = os.path.join(ROOT, "data", "registry", "dhn-nnr.yaml")
needs_corpus = pytest.mark.skipif(not os.path.exists(M2),
                                  reason="DHONE corpus not present")


def _synth_report(two_ended: bool = True, with_line: bool = True):
    spec = SynthSpec(
        m=0.42, fault="AG", rf=5.0,
        S=TerminalSpec(fs=1000.0, prefault_s=0.12, post_s=0.25, breaker_time_s=0.060),
        R=TerminalSpec(fs=1200.0, prefault_s=0.16, post_s=0.25, breaker_time_s=0.060,
                       sample_phase=0.37, clock_offset_s=1418.0))
    case = generate(spec)
    line = uniform_line("T", "Test line", spec.kv, spec.line_km, spec.z1_per_km,
                        spec.z0_per_km, spec.zs1_S, spec.zs0_S, spec.zs1_R,
                        spec.zs0_R) if with_line else None
    ends = ("S", "R") if two_ended else ("S",)
    ans = {e: analyse(case.records[e]) for e in ends}
    loc = None
    if line is not None:
        loc = locate(line, {e: TerminalInput(analysed=ans[e], end=e,
                                             zs1=line.terminals[e].zs1,
                                             zs0=line.terminals[e].zs0) for e in ends})
    feats = incident_features(ans, location=loc, line=line)
    rr = apply_rules(feats, load_rules())
    rep = build(ans, feats, rr, location=loc, line=line)
    render(rep)
    return rep


def _svgs(html: str):
    return re.findall(r"<svg .*?</svg>", html, re.S)


# --------------------------------------------------------------------------
def test_report_renders_with_no_template_placeholders_left():
    html = _synth_report().html
    assert "{{" not in html and "{%" not in html
    assert "<!DOCTYPE html>" in html
    assert html.count("class=\"page\"") == 2


def test_every_svg_is_well_formed_and_inside_its_frame():
    html = _synth_report().html
    svgs = _svgs(html)
    assert len(svgs) >= 3
    for s in svgs:
        ET.fromstring(s)                      # raises if malformed
        vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', s)
        w, h = float(vb.group(1)), float(vb.group(2))
        xs = [float(x) for x in re.findall(r'(?:x|cx|x1|x2)="(-?[\d.]+)"', s)]
        ys = [float(y) for y in re.findall(r'(?:y|cy|y1|y2)="(-?[\d.]+)"', s)]
        for blk in re.findall(r'points="([^"]+)"', s):
            for pt in blk.split():
                if "," in pt:
                    xs.append(float(pt.split(",")[0]))
                    ys.append(float(pt.split(",")[1]))
        assert max(xs) <= w + 5 and max(ys) <= h + 5
        assert min(xs) > -60 and min(ys) > -40


def test_no_nan_or_infinity_reaches_the_markup():
    """A NaN coordinate silently deletes a trace rather than erroring."""
    html = _synth_report().html
    assert not re.search(r"\b(nan|NaN|inf|Infinity)\b", html)


def test_two_ended_report_shows_both_terminals():
    html = _synth_report(two_ended=True).html
    assert "End S" in html and "End R" in html
    # four oscillogram panels: current and voltage at each end
    assert html.count("- currents") == 2 and html.count("- voltages") == 2


def test_single_ended_report_says_so_prominently():
    rep = _synth_report(two_ended=False)
    assert "Single-ended" in rep.html
    assert "3&ndash;15 %" in rep.html or "3-15" in rep.html


def test_report_without_a_line_definition_still_renders():
    """No registry entry means no location, and the report must say that."""
    rep = _synth_report(with_line=False)
    assert rep.location is None
    assert "No fault location was produced" in rep.html


def test_rules_that_could_not_be_judged_are_on_page_one():
    """A skipped rule is a recording gap and must not look like a pass."""
    html = _synth_report(two_ended=False).html
    assert "could not be judged" in html
    assert "not a healthy result" in html or "recording gap" in html


def test_ground_truth_capture_block_is_present_with_a_url():
    rep = _synth_report()
    assert rep.ground_truth_url
    assert rep.ground_truth_url in rep.html
    assert "Confirm the tower" in rep.html


def test_incident_id_is_stable_and_carries_the_line_and_time():
    import datetime as dt

    when = dt.datetime(2026, 4, 9, 3, 29, 2)
    a = incident_id("DHN-NNR", when, "abc")
    assert a == incident_id("DHN-NNR", when, "abc")
    assert a.startswith("DHN-NNR-20260409T032902-")
    assert a != incident_id("DHN-NNR", when, "xyz")


def test_graphics_degrade_rather_than_crash_on_empty_input():
    assert oscillogram([]) == ""
    assert phasor_diagram({}) == ""
    assert "No impedance trajectory" in rx_diagram([], [], 80.0)


def test_write_produces_a_self_contained_file(tmp_path):
    rep = _synth_report()
    out = tmp_path / "r.html"
    write(rep, str(out))
    html = out.read_text(encoding="utf-8")
    assert len(html) > 20000
    # Self-contained: nothing is fetched at render time. The SVG xmlns is a
    # namespace identifier, not a resource, so it is excluded rather than the
    # test being weakened to "no http anywhere".
    assert "<script" not in html
    assert "@import" not in html
    assert not re.search(r'<(link|img|iframe|object|embed)\b', html)
    assert not re.search(r'\bsrc\s*=', html)
    assert "url(" not in html
    externals = [u for u in re.findall(r'https?://[^\s"\'<>]+', html)
                 if u != rep.ground_truth_url
                 and not u.startswith("http://www.w3.org/")]
    assert not externals, externals


# --------------------------------------------------------------------------
@needs_corpus
def test_real_record_report_includes_the_relay_characteristic():
    line = load_line(LINE)
    rec = read_comtrade(M2, terminal_end="S")
    check(rec, nominal_kv=line.kv)
    an = analyse(rec, vt_type="CVT")
    st = load_settings(RIO)
    loc = locate(line, {"S": TerminalInput(analysed=an, end="S",
                                           zs1=line.terminals["S"].zs1,
                                           zs0=line.terminals["S"].zs0)})
    feats = incident_features({"S": an}, location=loc, line=line,
                              settings={"S": st}, z2_time_s=0.45)
    rr = apply_rules(feats, load_rules())
    rep = build({"S": an}, feats, rr, location=loc, line=line, settings={"S": st})
    render(rep)
    # six zone polygons from the real settings export, plus the trajectory
    assert rep.html.count("<polygon") == 6
    assert "Z1" in rep.html and "Z1B" in rep.html
    assert "measured" in rep.html
    # the backup findings from this record reach page 1 or the full list
    assert "BU-03" in rep.html and "BU-04" in rep.html
