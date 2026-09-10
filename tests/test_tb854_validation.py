"""Bounded project validation linked in TB854_VALIDATION_MATRIX.md.

These are independently constructed circuit/diagnostic fixtures, not CIGRE
benchmarks. They add no section, coupled, distributed or acquisition physics.
"""
import cmath
import math

import numpy as np
import pytest

from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc import ensemble
from dranalyser.faultloc.estimators import (
    Estimate, e1_reactance, e2_takagi, e3_modified_takagi, e4_synchronised,
    e5_unsynchronised, loop_quantities,
)
from dranalyser.registry.model import k0_from_impedances, uniform_line
from dranalyser.synth.generator import SynthSpec, generate


@pytest.mark.parametrize("phase", "ABC")
def test_ground_loop_matches_phase_impedance_network(phase):
    # Transposed phase network: diagonal (Z0+2Z1)/3 = 5+12j,
    # off-diagonal (Z0-Z1)/3 = 3+6j. No estimator equation generates V.
    z1, z0 = 2+6j, 11+24j
    currents = np.roll(np.array([9-2j, -2+3j, 1-1j]), "ABC".index(phase))
    zabc = np.full((3, 3), 3+6j)
    np.fill_diagonal(zabc, 5+12j)
    voltages = 0.375 * zabc @ currents  # bolted phase at a known chainage
    vph = dict(zip("ABC", voltages, strict=True))
    iph = dict(zip("ABC", currents, strict=True))
    vl, il, _ = loop_quantities(vph, iph, sum(currents)/3, k0_from_impedances(z1, z0), phase+"G")
    for est in (e1_reactance(vl, il, z1), e2_takagi(vl, il, currents["ABC".index(phase)], z1)):
        assert est.ok and est.m == pytest.approx(0.375, abs=1e-12)
    # Sensitivity control: sequence current treated as residual is measurably wrong.
    wrong_loop = iph[phase] + k0_from_impedances(z1, z0) * sum(currents)/3
    assert abs(e1_reactance(vl, wrong_loop, z1).m - 0.375) > 0.05


@pytest.mark.parametrize("imaginary", [-0.4, 0.4])
def test_e4_preserves_signed_distance_and_imaginary_diagnostic(imaginary):
    # Equal real voltage drops give m=-0.3. An extra differential voltage
    # j*imaginary*Z*(IS+IR) injects only an imaginary inconsistency.
    z, is_, ir, vf = 1+2j, 2+0j, 3+0j, 7-1j
    vs, vr = vf - 0.3*z*is_, vf + 1.3*z*ir
    vs += 1j*imaginary*z*(is_+ir)
    est = e4_synchronised(vs, is_, vr, ir, z)
    assert est.ok and est.m == pytest.approx(-0.3, abs=1e-12)
    assert est.residual == pytest.approx(0.4, abs=1e-12)
    assert est.diagnostics["m_imag"] == pytest.approx(imaginary, abs=1e-12)
    assert est.diagnostics["m_imag_abs"] == pytest.approx(0.4, abs=1e-12)


def _passive_sequence_network(m):
    # Negative-sequence source EMFs are zero. Solve each branch from a
    # prescribed fault-node voltage through its line segment and source Z.
    # This uses branch Ohm's law, no synth generator or E5 root helper.
    z, zs, zr, vf = 3+40j, 4+12j, 9+20j, 100+40j
    is_, ir = -vf/(zs+m*z), -vf/(zr+(1-m)*z)
    return -zs*is_, is_, -zr*ir, ir, z


@pytest.mark.parametrize("m", [0.17, 0.5, 0.83])
@pytest.mark.parametrize("angle", [-math.pi, -1.13, 0.0, 1.13, math.pi])
def test_two_ended_passive_network_rotation_and_terminal_reversal(m, angle):
    vs, is_, vr, ir, z = _passive_sequence_network(m)
    aligned = e4_synchronised(vs, is_, vr, ir, z)
    reversed_e4 = e4_synchronised(vr, ir, vs, is_, z)
    assert aligned.ok and aligned.m == pytest.approx(m, abs=1e-10)
    assert reversed_e4.ok and reversed_e4.m == pytest.approx(1-m, abs=1e-10)
    rot = cmath.exp(1j*angle)
    windows = [[value]*8 for value in (vs, is_, vr*rot, ir*rot)]
    forward = e5_unsynchronised(*windows, z)
    reverse = e5_unsynchronised(*windows[2:], *windows[:2], z)
    assert forward.ok and reverse.ok
    assert forward.m == pytest.approx(m, abs=1e-10)
    assert reverse.m == pytest.approx(1-m, abs=1e-10)
    # Compare circularly at +/-180 degrees.
    assert cmath.exp(1j*math.radians(forward.diagnostics["delta_deg"])) == pytest.approx(rot.conjugate())


def test_e5_selects_stable_angle_when_two_in_line_branches_compete():
    # Diagnostic counterexample, not a passive-network accuracy benchmark.
    # At m=.6 the two fault-point voltages are f and -f at every sample.
    # At m=.4 their magnitudes also match, but the angle varies with Im(f).
    # The correct branch must be HIGH so ignoring stability cannot pass by
    # taking the first (low) candidate.
    f = np.array([-0.3+1j*y for y in (-0.04, 0.01, 0.06, 0.12)])
    vs, is_, vr, ir = 1.2+f, np.full(4, 2+0j), 0.4-f, np.ones(4, complex)
    for m in (0.4, 0.6):
        assert np.abs(vs-m*is_) == pytest.approx(np.abs(vr-(1-m)*ir))
    wrong_angles = np.angle((vs-0.4*is_)/(vr-0.6*ir))
    assert np.ptp(wrong_angles) > 0.5
    est = e5_unsynchronised(vs, is_, vr, ir, 1+0j)
    assert est.ok and est.m == pytest.approx(0.6, abs=1e-12)
    assert est.diagnostics["root_separation"] == pytest.approx(0.2, abs=1e-12)
    assert est.diagnostics["delta_std_deg"] < 1e-5


def test_e5_root_separation_exposes_but_does_not_resolve_ambiguity():
    # Both .2 and 1/3 fit the same constant observations with fixed angles.
    # Test diagnostic evidence only: the current method DOES NOT refuse ties.
    # No unique-location validation is claimed for this fixture (matrix V06).
    for m in (0.2, 1/3):
        assert abs(0.6-2*m) == pytest.approx(abs(0.6-(1-m)))
    est = e5_unsynchronised([0.6]*6, [2]*6, [0.6]*6, [1]*6, 1+0j)
    assert est.diagnostics["root_separation"] == pytest.approx(2/15, abs=1e-12)
    assert est.residual < 1e-12
    assert est.diagnostics["delta_std_deg"] < 1e-5
    # This residual/stability combination cannot certify either candidate.


@pytest.mark.parametrize("method", ["E1", "E2", "E3", "E4", "E5"])
def test_estimators_refuse_absent_required_current(method):
    z = 3+40j
    calls = {
        "E1": lambda: e1_reactance(1, 0, z),
        "E2": lambda: e2_takagi(1, 2, 0, z),
        "E3": lambda: e3_modified_takagi(1, 2, 0, z, 3*z, z, z),
        "E4": lambda: e4_synchronised(1, 0, 1, 0, z),
        "E5": lambda: e5_unsynchronised([1]*6, [0]*6, [1]*6, [0]*6, z),
    }
    est = calls[method]()
    assert not est.ok and math.isnan(est.m) and est.reason


@pytest.mark.parametrize("scale", [0.8, 1.2])
def test_wrong_line_impedance_can_bias_e4_with_zero_residual(scale):
    # Both ends feed a bolted sequence fault. V_S = .3*Z*I_S and
    # V_R = .7*Z*I_R. Equal currents and a common Z scale error yield
    # .5 + (.3-.5)/scale; this is unidentifiable from Im(m) alone.
    z, current = 3+40j, 2-1j
    est = e4_synchronised(0.3*z*current, current, 0.7*z*current, current, scale*z)
    expected = 0.25 if scale == 0.8 else 1/3
    assert est.ok and est.m == pytest.approx(expected, abs=1e-12)
    assert est.residual < 1e-12
    assert abs(est.m-0.3) > 0.03  # shared parameter bias is not a confidence interval


@pytest.fixture
def terminal_and_line():
    case = generate(SynthSpec(m=0.4, fault="AG", rf=1.0))
    ti = ensemble.TerminalInput(analyse(case.records["S"]), "S")
    return ti, uniform_line("T", "test", 220, 100, 0.03+0.4j, 0.25+1.2j)


@pytest.mark.parametrize("m,terminal", [(-0.1, "local"), (1.1, "remote")])
def test_external_indication_is_distinct_from_impossible_distance(monkeypatch, terminal_and_line, m, terminal):
    ti, line = terminal_and_line
    monkeypatch.setattr(ensemble, "_single_ended", lambda *args: [Estimate("E1", m, 0, ends="single")])
    res = ensemble.locate(line, {"S": ti})
    assert res.ok and res.m == pytest.approx(m)  # signed diagnostic survives
    assert any("beyond the " + terminal in c and "should not be patrolled" in c for c in res.caveats)
    assert not any("input problem" in c for c in res.caveats)
    # Existing implementation still clamps km/towers. This is NOT validated
    # external-fault chainage; see the explicit report-safety gap in V10.


def test_remote_only_estimate_is_mapped_to_s_without_argument_order_inference(monkeypatch, terminal_and_line):
    ti, line = terminal_and_line
    ti.end = "R"  # explicit identity
    monkeypatch.setattr(ensemble, "_single_ended", lambda *args: [Estimate("E1", 0.2, 0, ends="single")])
    res = ensemble.locate(line, {"R": ti})
    assert res.ok and res.method == "E1@R"
    assert res.m == pytest.approx(0.8)
    assert res.km_from_S == pytest.approx(80) and res.km_from_R == pytest.approx(20)


@pytest.mark.parametrize("s_good,r_good", [(False, False), (True, False), (False, True), (True, True)])
def test_e4_requires_both_clock_quality_flags(terminal_and_line, s_good, r_good):
    ti, line = terminal_and_line
    # Gating fixture only: duplicate analysed data is NOT a genuine end pair.
    remote = ensemble.TerminalInput(ti.analysed, "R", clock_good=r_good)
    ti.clock_good = s_good
    e4 = ensemble._two_ended(ti, remote, line, "AG")[0]
    assert e4.method == "E4"
    assert e4.ok == (s_good and r_good)
    if not e4.ok:
        assert "clock quality not established at both ends" in e4.reason
