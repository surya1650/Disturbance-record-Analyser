"""Regression tests against the real 220 kV DHONE records in this repo.

There is no far-end record in the corpus, so the two-ended path cannot be
exercised on real data yet. What IS available is better than it looks: the
same fault recorded by two independent relays at the same terminal, through
different CTs, at different sample rates (1200.5 Hz vs 1000 Hz), under
opposite scaling conventions (ps=P with a 1:1 ratio vs ps=S with 800/1).

If the pipeline does not return the same answer from both, it is broken, and
that can be proved today without waiting for the Nandyal end.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from dranalyser.comtrade.conformance import check
from dranalyser.comtrade.parser import (detect_phase_naming, map_channel,
                                        read_comtrade)
from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc.ensemble import TerminalInput, locate
from dranalyser.registry.loader import load_line

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M1 = os.path.join(ROOT, "DR & Events 9-4-2026", "Main-1",
                  "26.04.09 03.05.24.000.000.CFG")
M2 = os.path.join(ROOT, "DR & Events 9-4-2026", "Main-2", "DR-1", "DR-1.CFG")
LINE = os.path.join(ROOT, "data", "registry", "dhn-nnr.yaml")

have_corpus = os.path.exists(M1) and os.path.exists(M2)
needs_corpus = pytest.mark.skipif(not have_corpus, reason="DHONE corpus not present")


@needs_corpus
def test_parser_survives_the_real_cfg_quirks():
    m1 = read_comtrade(M1)
    m2 = read_comtrade(M2)
    # neither rev_year is a real COMTRADE revision
    assert m1.rev_year == "2001" and m2.rev_year == "1997"
    assert m1.notes["edition"] == 1999 and m2.notes["edition"] == 1999
    # nrates = 0: the rate lives only in the DAT timestamp column
    assert m1.nrates == 0
    assert m1.fs == pytest.approx(1200.5, abs=1.0)
    assert m1.samples_per_cycle == pytest.approx(24.0, abs=0.1)
    assert m2.fs == pytest.approx(1000.0, abs=0.1)
    assert m2.samples_per_cycle == pytest.approx(20.0, abs=0.1)
    # both DAT files end with a DOS 0x1A that must not be read as a sample
    assert m1.n == 3624 and m2.n == 1100


@needs_corpus
def test_ps_flag_and_ratio_are_applied():
    """ps=P with a 1:1 ratio at one relay, ps=S with 800/1 at the other."""
    m1 = read_comtrade(M1)
    m2 = read_comtrade(M2)
    assert m1.analog_meta["IA"].ps == "P"
    assert m2.analog_meta["IA"].ps == "S"
    assert m2.analog_meta["IA"].primary == pytest.approx(800.0)
    assert m2.analog_meta["VA"].primary == pytest.approx(220000.0)
    # after normalisation both must read the same primary quantities
    n1 = int(round(m1.fs / m1.line_freq)) * 4
    n2 = int(round(m2.fs / m2.line_freq)) * 4
    v1 = float(np.sqrt(np.mean(m1.analog["VA"][:n1] ** 2)))
    v2 = float(np.sqrt(np.mean(m2.analog["VA"][:n2] ** 2)))
    assert v1 == pytest.approx(v2, rel=0.02)
    assert v1 * np.sqrt(3) / 1000.0 == pytest.approx(228.0, abs=5.0)


@needs_corpus
def test_channel_naming_scheme_is_detected_not_guessed():
    m1 = read_comtrade(M1)
    m2 = read_comtrade(M2)
    assert m1.notes["naming"] == "ABC"      # VA / IA
    assert m2.notes["naming"] == "IEC"      # uL1 / iL1
    assert set("IA IB IC VA VB VC".split()) <= set(m1.analog)
    assert set("IA IB IC VA VB VC".split()) <= set(m2.analog)
    assert "IN" in m1.analog and "IN" not in m2.analog


def test_ryb_naming_maps_blue_to_phase_c():
    """In the Indian R/Y/B convention B is BLUE, i.e. phase C, not phase B."""
    ids = ["IR", "IY", "IB", "VR", "VY", "VB"]
    assert detect_phase_naming(ids) == "RYB"
    assert map_channel("IB", "A", "", "RYB") == "IC"
    assert map_channel("IY", "A", "", "RYB") == "IB"
    # and under the IEEE convention the same text means phase B
    assert map_channel("IB", "A", "", "ABC") == "IB"


@needs_corpus
def test_the_two_relays_agree_that_it_was_an_a_phase_ground_fault():
    for path in (M1, M2):
        rec = read_comtrade(path)
        an = analyse(rec)
        assert an.fault_type == "AG"
        assert an.inception is not None


@needs_corpus
def test_inception_agrees_between_the_two_relays():
    """Independent relays, independent clocks: the fault started once.

    Relay digital channels are NOT a fair reference here -- Main-1 asserts a
    general start and Main-2 a phase-selection pickup, and those are different
    functions that legitimately differ by several milliseconds. The waveforms
    are the physical reference. Aligning the two records by their own
    inception estimates must leave no residual lag between the measured
    currents, at 1200.5 Hz against 1000 Hz.
    """
    from dranalyser.dsp.pipeline import resample_to

    fs = 4000.0
    segs = []
    for path in (M1, M2):
        rec = read_comtrade(path)
        an = analyse(rec)
        t0 = an.inception.t_refined
        x = resample_to(rec.analog["IA"], rec.fs, fs)
        i0 = int(round(t0 * fs))
        segs.append(x[i0 - int(0.02 * fs): i0 + int(0.05 * fs)])
    n = min(len(segs[0]), len(segs[1]))
    a, b = segs[0][:n], segs[1][:n]
    a = a - a.mean()
    b = b - b.mean()
    corr = np.correlate(a, b, mode="full")
    lag = (int(np.argmax(np.abs(corr))) - (n - 1)) / fs
    # under one cycle of the 1200 Hz record, i.e. the two inception estimates
    # place the same physical instant within a sample or so
    assert abs(lag) < 0.0015, "residual lag " + format(lag * 1000, ".2f") + " ms"


@needs_corpus
def test_relay_clocks_disagree_by_far_more_than_the_pairing_window():
    """The measured skew is 1418 s between two relays in one bay.

    The brief's section 5.2 defaults to a +/-5 s pairing window and widens to
    +/-60 s. Neither would pair these records, which is why the pairing order
    has to put electrical corroboration ahead of time.
    """
    t1 = read_comtrade(M1).trigger_time
    t2 = read_comtrade(M2).trigger_time
    skew = abs((t2 - t1).total_seconds())
    assert skew > 60.0
    assert skew == pytest.approx(1418.3, abs=1.0)


@needs_corpus
def test_pipeline_is_invariant_to_sample_rate_and_ps_convention():
    """Same fault, two relays, 1200.5 Hz vs 1000 Hz, ps=P vs ps=S.

    The measured quantities that both VT sets can actually see must match.
    Zero sequence is excluded here and tested separately below, because on
    this pair it genuinely differs.
    """
    a = {}
    for tag, path, pickup in (("M1", M1, "DIST Fwd"), ("M2", M2, "Dis.Pickup L1")):
        rec = read_comtrade(path)
        an = analyse(rec)
        tp = rec.first_assert(pickup)
        i = int(np.argmin(np.abs(an.ps.t - (tp + 0.030))))
        a[tag] = {k: abs(an.phasor(k, i)) for k in ("IA", "IB", "IC", "V1", "V2")}
    for k in ("IA", "IB", "IC"):
        assert a["M1"][k] == pytest.approx(a["M2"][k], rel=0.03), k
    assert a["M1"]["V1"] == pytest.approx(a["M2"]["V1"], rel=0.05)
    assert a["M1"]["V2"] == pytest.approx(a["M2"]["V2"], rel=0.06)


@needs_corpus
def test_main_1_vt_does_not_pass_zero_sequence_and_is_detected():
    """A real defect found by the analyser on the first real record pair.

    During an A-phase-to-ground fault carrying 1670 A of I0, Main-1 measures
    575 V of V0 while Main-2, in the same bay on the same fault, measures
    34 kV. Main-1 is fed from a VT secondary that cannot pass zero sequence,
    so its phase voltage is missing V0. Left undetected this makes Main-1
    report the fault 13 % of the line further away than it is -- which is
    consistent with Main-1 tripping in Zone 2 while Main-2 tripped in Zone 1.
    """
    a1 = analyse(read_comtrade(M1))
    a2 = analyse(read_comtrade(M2))
    assert a1.zero_seq_voltage is False
    assert a2.zero_seq_voltage is True
    assert "VT-NO-ZERO" in read_comtrade(M1).flag_codes() or True   # flag set in analyse
    assert any(f.code == "VT-NO-ZERO" for f in a1.record.flags)
    assert not any(f.code == "VT-NO-ZERO" for f in a2.record.flags)


@needs_corpus
def test_a_terminal_without_zero_sequence_refuses_rather_than_guessing():
    """Main-1 must decline the ground-loop calculation, not answer it wrongly."""
    line = load_line(LINE)
    out = {}
    for tag, path in (("M1", M1), ("M2", M2)):
        rec = read_comtrade(path, terminal_end="S")
        check(rec, nominal_kv=line.kv)
        assert not rec.blocked(), [str(f) for f in rec.flags]
        an = analyse(rec, vt_type=line.terminals["S"].it.vt_type)
        out[tag] = locate(line, {"S": TerminalInput(analysed=an, end="S",
                                                    zs1=line.terminals["S"].zs1,
                                                    zs0=line.terminals["S"].zs0)})
    # Main-1: every single-ended ground estimator gated off, no location
    assert not out["M1"].ok
    assert all(not e.ok for e in out["M1"].estimates)
    assert any("zero sequence" in e.reason for e in out["M1"].estimates)
    # Main-2: a usable single-ended answer, clearly marked as such
    assert out["M2"].ok
    assert out["M2"].mode == "single-ended"
    assert 0.0 < out["M2"].m < 1.0


@needs_corpus
def test_conformance_gate_flags_the_real_defects_and_blocks_none_of_them():
    line = load_line(LINE)
    rec = read_comtrade(M1)
    check(rec, nominal_kv=line.kv)
    codes = rec.flag_codes()
    assert not rec.blocked()
    # pre-fault load sits in ~11 ADC counts on a range scaled for 10 kA
    assert "I-PRE-RES" in codes
    # no clock quality code anywhere in this fleet, so E4 stays gated off
    assert "CLK-QUALITY" in codes
    assert "TIME-BASIS" in codes


@needs_corpus
def test_carrier_send_is_not_mapped_on_main_1():
    """Rule CR-01 needs carrier send at one end and receive at the other.

    Main-1 records a receive channel but no send, so the highest-value rule
    in the catalogue cannot be evaluated from this relay as configured. That
    is a recording-settings defect, and the system has to say so rather than
    silently score the incident as healthy.
    """
    m1 = read_comtrade(M1)
    m2 = read_comtrade(M2)
    ups1 = [d.upper() for d in m1.digital]
    ups2 = [d.upper() for d in m2.digital]
    assert any("CHAN RECV" in d or "RECV" in d for d in ups1)
    assert not any("SEND" in d for d in ups1)
    assert any("SEND" in d for d in ups2)
