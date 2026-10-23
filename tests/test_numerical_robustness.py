"""Independent algebraic counterexamples, not field accuracy benchmarks."""
import math

import numpy as np
import pytest

from dranalyser.faultloc.estimators import e4_synchronised, e5_roots, e5_unsynchronised, stable_quadratic
from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc.ensemble import TerminalInput, locate
from dranalyser.registry.model import uniform_line
from dranalyser.synth.generator import SynthSpec, TerminalSpec, generate


@pytest.mark.parametrize('scale', [1e-300, 1e-200, 1, 1e200, 1e300])
def test_real_roots_are_invariant_to_finite_polynomial_scaling(scale):
    # (m-1)(m-2), no production root helper constructs the expectation.
    roots, _ = stable_quadratic(scale, -3*scale, 2*scale)
    assert roots == pytest.approx([1, 2], rel=1e-12)


def test_a_positive_quadratic_minimum_is_not_a_real_root():
    # (m-.5)^2 + .01 > 0 for every real m.
    roots, reason = stable_quadratic(1, -1, .26)
    assert roots == []
    assert 'no real' in reason


@pytest.mark.parametrize('scale', [1e-200, 1e200])
def test_e5_forms_constraint_coefficients_without_squaring_overflow_or_underflow(scale):
    # |.9-m*2| = |.7-(1-m)| gives 3*(m-.4)*(m-.6)=0.
    roots, _, _ = e5_roots(.9*scale, 2*scale, .7*scale, scale, 1)
    assert roots == pytest.approx([.4, .6], abs=1e-12)


@pytest.mark.parametrize('coefficients', [(math.inf, 1, 1), (1, math.nan, 1), (1, 1, -math.inf)])
def test_nonfinite_polynomials_have_no_usable_roots(coefficients):
    roots, _ = stable_quadratic(*coefficients)
    assert roots == []


def test_aligned_estimate_never_marks_nonfinite_phasors_as_ok():
    estimate = e4_synchronised(complex(math.nan), 1, 1, 1, 1+1j)
    assert not estimate.ok and math.isnan(estimate.m)


def test_e5_refuses_magnitudes_that_cannot_intersect():
    # |.5+.2j-m| >= .2, while the other end has magnitude .1.
    estimate = e5_unsynchronised([.5+.2j]*8, [1]*8, [.1]*8, [0]*8, 1)
    assert not estimate.ok and math.isnan(estimate.m)
    assert estimate.diagnostics.get('inconsistent_window')


def test_e5_does_not_drop_one_inconsistent_observation_from_a_window():
    z, zs, zr, vf, m = 3+40j, 4+12j, 9+20j, 100+40j, .3
    is_, ir = -vf/(zs+m*z), -vf/(zr+(1-m)*z)
    window = [np.full(8, value, complex) for value in (-zs*is_, is_, -zr*ir, ir)]
    # One observation has no real solution; seven good samples cannot hide it.
    for values, bad in zip(window, [.5+.2j, 1/z, .1, 0], strict=True):
        values[4] = bad
    estimate = e5_unsynchronised(*window, z)
    assert not estimate.ok and math.isnan(estimate.m)
    assert estimate.diagnostics.get('inconsistent_window')


def test_e5_cannot_authorize_an_undefined_recovered_fault_point_angle():
    # Both recovered fault voltages vanish at m=.3, so their relative phase
    # cannot identify clock rotation. Low residual does not restore that phase.
    estimate = e5_unsynchronised([.6]*8, [2]*8, [.7]*8, [1]*8, 1)
    assert not estimate.ok and math.isnan(estimate.m)
    assert estimate.diagnostics.get('undefined_angle')


@pytest.mark.parametrize('problem', ['inconsistent', 'undefined', 'nonfinite'])
@pytest.mark.parametrize('aligned', [False, True])
def test_incident_preserves_structural_e5_refusal_unless_aligned_e4_is_usable(problem, aligned):
    # Counterexample integration: real DSP and single-ended methods still run.
    # Only the selected sequence constraint is changed, not mocked estimators.
    def recorder():
        return TerminalSpec(fs=2400, prefault_s=.12, post_s=.5, trip_delay_s=.3,
                            noise_pct=0, cvt_transient=False, adc_bits=24)
    case = generate(SynthSpec(m=.3, fault='AG', rf=1, dc_offset=False, S=recorder(), R=recorder()))
    line = uniform_line('TEST', 'Synthetic constraint integration', 220, 100, .03+.4j, .2+1.2j)
    quantities = ([.5+.001j, 1/line.z1, .0001, 0] if problem == 'inconsistent' else
                  [.6, 2/line.z1, .7, 1/line.z1])
    if problem == 'nonfinite':
        quantities[0] = complex(math.nan)
    terminals = {}
    for end, (voltage, current) in zip(('S', 'R'), (quantities[:2], quantities[2:]), strict=True):
        an = analyse(case.records[end])
        an.zero_seq_voltage = True  # synthetic phase-to-neutral inputs include V0
        an.ps.phasors['V2'][:] = voltage
        an.ps.phasors['I2'][:] = current
        terminals[end] = TerminalInput(an, end, clock_good=aligned)
    result = locate(line, terminals)
    e5 = next(e for e in result.estimates if e.method == 'E5')
    assert not e5.ok
    if aligned and problem != 'nonfinite':
        assert result.ok and result.mode == 'two-ended' and 'E4' in result.method
    else:
        assert result.mode == 'none' and math.isnan(result.km_from_S)
        assert not result.towers and result.likely_tower is None
