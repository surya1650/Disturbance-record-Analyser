"""Maths first: every estimator is asserted against a known m before any
record is parsed. These tests need no data files."""
from __future__ import annotations

import cmath
import math

import numpy as np
import pytest

from dranalyser.faultloc.estimators import (e1_reactance, e2_takagi,
                                            e3_modified_takagi, e4_synchronised,
                                            e5_unsynchronised, loop_quantities,
                                            stable_quadratic)
from dranalyser.registry.model import (k0_from_impedances, k0_from_siemens,
                                       uniform_line)
from dranalyser.synth.generator import SynthSpec, _solve_phasors, phase_to_seq

FAULTS = ("AG", "BG", "CG", "AB", "BC", "CA", "ABG", "BCG", "CAG", "ABC")


def _seq(v):
    return phase_to_seq(v)


def _two_ended_inputs(spec, rotate=0.0):
    ph = _solve_phasors(spec)
    rot = cmath.exp(1j * rotate)
    if spec.fault in ("ABC", "ABCG"):
        s = _seq(ph["VS"])[1] - _seq(ph["VS_pre"])[1]
        si = _seq(ph["IS"])[1] - _seq(ph["IS_pre"])[1]
        r = (_seq(ph["VR"])[1] - _seq(ph["VR_pre"])[1]) * rot
        ri = (_seq(ph["IR"])[1] - _seq(ph["IR_pre"])[1]) * rot
    else:
        s, si = _seq(ph["VS"])[2], _seq(ph["IS"])[2]
        r, ri = _seq(ph["VR"])[2] * rot, _seq(ph["IR"])[2] * rot
    return ph, s, si, r, ri


# --------------------------------------------------------------------------
def test_k0_siemens_conversion_matches_the_real_rio_file():
    """RE/RL = 1.020, XE/XL = 0.800, line angle 81 deg, from DR-1.rio."""
    k0 = k0_from_siemens(1.020, 0.800, 81.0)
    assert abs(k0) == pytest.approx(0.80610, abs=1e-4)
    assert math.degrees(cmath.phase(k0)) == pytest.approx(-2.4168, abs=0.005)
    # the naive reading of XE/XL as the k0 magnitude loses the angle entirely
    assert abs(cmath.phase(k0)) > math.radians(2.0)


def test_k0_round_trip():
    z1 = complex(3.0, 40.0)
    z0 = complex(25.0, 120.0)
    k0 = k0_from_impedances(z1, z0)
    assert z1 * (1.0 + 3.0 * k0) == pytest.approx(z0, rel=1e-12)


def test_m_to_km_walks_reactance_not_length():
    """A mixed-conductor line: half the length, but not half the reactance."""
    from dranalyser.registry.model import Line, LineSection, Terminal

    secs = [LineSection(1, 0.0, 50.0, 0.03, 0.20, 0.25, 1.0),
            LineSection(2, 50.0, 100.0, 0.03, 0.60, 0.25, 1.5)]
    line = Line(id="MIX", name="mixed", kv=220, sections=secs,
                terminals={"S": Terminal("S", "S"), "R": Terminal("R", "R")})
    # Total X = 50*0.20 + 50*0.60 = 40 ohm. Section 1 holds only 10 of those
    # 40 ohm across half the LENGTH, so the reactive midpoint of the line is
    # at 66.7 km, not 50 km. A linear length conversion would be 16.7 km out
    # -- about 48 spans, which is the whole point of walking the sections.
    assert line.m_to_km(0.25) == pytest.approx(50.0, abs=1e-9)   # end of section 1
    assert line.m_to_km(0.5) == pytest.approx(66.6667, abs=1e-3)
    assert line.m_to_km(0.75) == pytest.approx(83.3333, abs=1e-3)
    assert line.km_to_m(line.m_to_km(0.4)) == pytest.approx(0.4, abs=1e-9)
    # and the naive linear conversion really is that far out
    assert abs(line.m_to_km(0.5) - 0.5 * line.length_km) > 16.0


# --------------------------------------------------------------------------
def test_stable_quadratic_degenerates_to_linear():
    roots, how = stable_quadratic(0.0, 2.0, -1.0)
    assert roots == pytest.approx([0.5])
    assert "linear" in how
    roots, how = stable_quadratic(1e-18, 2.0, -1.0)
    assert roots[0] == pytest.approx(0.5, abs=1e-9)


def test_stable_quadratic_avoids_catastrophic_cancellation():
    """Roots of a quadratic whose naive solution loses all precision."""
    a, b, c = 1.0, -1e8, 1.0
    roots, _ = stable_quadratic(a, b, c)
    assert min(roots) == pytest.approx(1e-8, rel=1e-6)
    assert max(roots) == pytest.approx(1e8, rel=1e-9)


# --------------------------------------------------------------------------
@pytest.mark.parametrize("m", [0.02, 0.25, 0.50, 0.52, 0.75, 0.98])
@pytest.mark.parametrize("fault", FAULTS)
def test_e5_is_exact_on_ideal_phasors_and_immune_to_sync_angle(m, fault):
    """E5 must recover m regardless of an arbitrary unknown clock offset."""
    spec = SynthSpec(m=m, fault=fault, rf=10.0)
    _, v2s, i2s, v2r, i2r = _two_ended_inputs(spec, rotate=1.13)
    est = e5_unsynchronised([v2s] * 6, [i2s] * 6, [v2r] * 6, [i2r] * 6, spec.z1_line)
    assert est.ok, est.reason
    assert est.m == pytest.approx(m, abs=1e-7)
    # the recovered angle is the injected one
    assert est.diagnostics["delta_deg"] == pytest.approx(-math.degrees(1.13), abs=0.01)


@pytest.mark.parametrize("m", [0.15, 0.5, 0.85])
@pytest.mark.parametrize("fault", FAULTS)
def test_e4_is_exact_when_time_aligned(m, fault):
    spec = SynthSpec(m=m, fault=fault, rf=3.0)
    _, v2s, i2s, v2r, i2r = _two_ended_inputs(spec, rotate=0.0)
    est = e4_synchronised(v2s, i2s, v2r, i2r, spec.z1_line)
    assert est.ok
    assert est.m == pytest.approx(m, abs=1e-9)
    # a real line gives a real m; the imaginary part is the quality metric
    assert est.residual < 1e-6


def test_e5_root_selection_prefers_the_stable_sync_angle():
    """Both quadratic roots can sit inside [0,1]; the wrong one is unstable."""
    spec = SynthSpec(m=0.5, fault="AG", rf=30.0)
    _, v2s, i2s, v2r, i2r = _two_ended_inputs(spec, rotate=0.4)
    est = e5_unsynchronised([v2s] * 12, [i2s] * 12, [v2r] * 12, [i2r] * 12,
                            spec.z1_line)
    assert est.m == pytest.approx(0.5, abs=1e-7)
    assert est.diagnostics["delta_std_deg"] < 1e-6


# --------------------------------------------------------------------------
def test_e1_shows_the_reactance_effect_and_e2_corrects_it():
    """The whole reason two-ended exists: single-ended is fooled by R_F."""
    spec = SynthSpec(m=0.90, fault="AG", rf=30.0)
    ph = _solve_phasors(spec)
    k0 = k0_from_impedances(spec.z1_line, spec.z0_line)
    vph = {p: ph["VS"][i] for i, p in enumerate("ABC")}
    iph = {p: ph["IS"][i] for i, p in enumerate("ABC")}
    vpre = {p: ph["VS_pre"][i] for i, p in enumerate("ABC")}
    ipre = {p: ph["IS_pre"][i] for i, p in enumerate("ABC")}
    vl, il, _ = loop_quantities(vph, iph, _seq(ph["IS"])[0], k0, "AG")
    _, ilp, _ = loop_quantities(vpre, ipre, _seq(ph["IS_pre"])[0], k0, "AG")

    r1 = e1_reactance(vl, il, spec.z1_line)
    r2 = e2_takagi(vl, il, il - ilp, spec.z1_line)
    assert abs(r1.m - 0.90) > 0.02          # E1 is pulled well off
    assert abs(r2.m - 0.90) < abs(r1.m - 0.90)   # Takagi recovers most of it


def test_e2_denominator_uses_the_compensated_loop_current():
    """The brief writes I_S; using the raw phase current is a large error."""
    spec = SynthSpec(m=0.6, fault="AG", rf=0.5)
    ph = _solve_phasors(spec)
    k0 = k0_from_impedances(spec.z1_line, spec.z0_line)
    vph = {p: ph["VS"][i] for i, p in enumerate("ABC")}
    iph = {p: ph["IS"][i] for i, p in enumerate("ABC")}
    vpre = {p: ph["VS_pre"][i] for i, p in enumerate("ABC")}
    ipre = {p: ph["IS_pre"][i] for i, p in enumerate("ABC")}
    vl, il, _ = loop_quantities(vph, iph, _seq(ph["IS"])[0], k0, "AG")
    _, ilp, _ = loop_quantities(vpre, ipre, _seq(ph["IS_pre"])[0], k0, "AG")
    isup = il - ilp

    good = e2_takagi(vl, il, isup, spec.z1_line)
    bad = e2_takagi(vl, iph["A"], isup, spec.z1_line)   # raw phase current
    assert good.m == pytest.approx(0.6, abs=0.02)
    assert abs(bad.m - 0.6) > 0.10


def test_e3_beta_sign_reduces_the_error_rather_than_doubling_it():
    """A flipped beta applies the homogeneity correction backwards."""
    spec = SynthSpec(m=0.8, fault="AG", rf=25.0,
                     zs0_S=complex(2.0, 8.0), zs0_R=complex(9.0, 60.0))
    ph = _solve_phasors(spec)
    k0 = k0_from_impedances(spec.z1_line, spec.z0_line)
    vph = {p: ph["VS"][i] for i, p in enumerate("ABC")}
    iph = {p: ph["IS"][i] for i, p in enumerate("ABC")}
    i0 = _seq(ph["IS"])[0]
    vl, il, _ = loop_quantities(vph, iph, i0, k0, "AG")
    est = e3_modified_takagi(vl, il, i0, spec.z1_line, spec.z0_line,
                             spec.zs0_S, spec.zs0_R)
    e1 = e1_reactance(vl, il, spec.z1_line)
    assert est.ok
    assert abs(est.m - 0.8) < abs(e1.m - 0.8)
