"""Independent direct-kernel algebra and adversarial complex error circles."""
import importlib
import json

import numpy as np
import pytest

from dranalyser.dsp.core import sliding_dft


def budget():
    return importlib.import_module('dranalyser.dsp.sequence_budget')


def direct_kernel(fs, freq, tau, half, first):
    n = round(fs/freq)
    n = max(n//2, 2) if half else n
    start = 0 if first else n+2
    count = start+n
    b = np.exp(-(1/fs)/max(tau, 1e-6)) if tau is not None else 0
    transform = np.eye(count)-b*np.eye(count, k=-1)
    transform[0, 0] = 1-b
    t = np.arange(count)/fs
    design = np.column_stack([np.cos(2*np.pi*freq*t), np.sin(2*np.pi*freq*t)])
    inverse = np.linalg.pinv((transform@design)[start:])
    return (inverse[0]-1j*inverse[1])@transform[start:]/np.sqrt(2)


@pytest.mark.parametrize('fs,freq', [(1200, 50), (3500, 48), (2600, 52), (4800, 53)])
@pytest.mark.parametrize('tau', [None, 0, .02, .08])
@pytest.mark.parametrize('half', [False, True])
def test_direct_kernel_includes_both_mimic_boundaries_and_initialization(fs, freq, tau, half):
    result = budget().dft_noise_radius(fs, freq, .003, tau=tau, half_cycle=half, uniform_grid=True)
    assert result['status'] == 'conditional_bound' and result['authorizes_location'] is False
    for first in (False, True):
        weights = direct_kernel(fs, freq, tau, half, first)
        assert sum(abs(weights)) <= result['coefficient_l1_upper_bound']+1e-12
        rng = np.random.default_rng(854)
        signal = rng.normal(size=len(weights))*1000
        noise = rng.uniform(-.003, .003, len(weights))
        t = np.arange(len(weights))/fs
        observed = sliding_dft(signal+noise, t, fs, freq, half_cycle=half, tau=tau)[-1]
        reference = sliding_dft(signal, t, fs, freq, half_cycle=half, tau=tau)[-1]
        assert observed == pytest.approx(weights@(signal+noise), abs=1e-8)
        assert abs(observed-reference) <= result['radius_primary_a']+1e-8
    json.dumps(result, allow_nan=False)


def phases(i1, i2):
    a = np.exp(2j*np.pi/3)
    return np.array([i1+i2, a*a*i1+a*i2, a*i1+a*a*i2])


def negative(values):
    a = np.exp(2j*np.pi/3)
    return (values[0]+a*a*values[1]+a*values[2])/3


def test_adversarial_phase_errors_attain_triangle_and_relative_bound():
    a = np.exp(2j*np.pi/3)
    measured = phases(1000, 20*np.exp(.2j))
    radii = [.3, .6, .9]
    errors = np.array([radii[0], a*radii[1], a*a*radii[2]])*np.exp(.2j)
    true = measured-errors
    result = budget().i2_budget(measured, radii, provenance='Exact synthetic complex error circles')
    assert result['status'] == 'bounded_under_assumptions'
    assert result['input_i2_radius_primary_a'] == pytest.approx(.6)
    assert abs(negative(measured)-negative(true)) == pytest.approx(.6)
    actual_relative = abs(negative(measured)-negative(true))/abs(negative(true))
    assert actual_relative <= result['relative_error_bound']+1e-12
    assert actual_relative == pytest.approx(.6/19.4)
    assert result['authorizes_location'] is False


@pytest.mark.parametrize('scale', [1e-6, 1, 1e6])
def test_random_correlated_errors_stay_inside_conditional_interval(scale):
    rng = np.random.default_rng(4854)
    measured = phases(100*scale, 20*scale*np.exp(.7j))
    radii = np.array([.2, .4, .7])*scale
    out = budget().i2_budget(measured, radii, provenance='Known bounded perturbations; no independence assumption')
    lo, hi = out['true_i2_magnitude_interval_primary_a']
    for _ in range(200):
        errors = radii*rng.uniform(size=3)*np.exp(2j*np.pi*rng.uniform(size=3))
        true = negative(measured-errors)
        assert lo-1e-9*scale <= abs(true) <= hi+1e-9*scale
        assert abs(negative(measured)-true)/abs(true) <= out['relative_error_bound']+1e-10


def test_balanced_weak_and_unknown_bounds_never_authorize():
    balanced = budget().i2_budget(phases(1000, 0), [.1]*3, provenance='Synthetic cap')
    assert balanced['status'] == 'withheld' and balanced['relative_error_bound'] is None
    weak = budget().i2_budget(phases(1000, .01), [.001]*3, provenance='Synthetic cap')
    assert weak['status'] == 'withheld'
    assert budget().i2_budget(phases(1000, 100), None)['status'] == 'unsupported'
    assert budget().i2_budget(phases(1000, 100), [0]*3)['status'] == 'unsupported'
    known_zero = budget().i2_budget(phases(1000, 100), [0]*3, provenance='Explicit zero synthetic input error')
    assert known_zero['status'] == 'bounded_under_assumptions'
    assert known_zero['authorizes_location'] is False


@pytest.mark.parametrize('currents,radii,provenance', [
    ([1, 2], [0]*3, 'cap'), ([1]*3, [-1, 0, 0], 'cap'),
    ([1]*3, [np.nan]*3, 'cap'), ([1]*3, [np.inf]*3, 'cap'),
    ([1, 2, complex(np.nan, 0)], [0]*3, 'cap'), ([1]*3, [False]*3, 'cap'),
    ([1]*3, [0]*3, False), ([complex(1.7e308, 1.7e308)]*3, [0]*3, 'cap')])
def test_invalid_sequence_inputs_are_finite_unsupported(currents, radii, provenance):
    out = budget().i2_budget(currents, radii, provenance=provenance)
    assert out['status'] == 'unsupported' and out['authorizes_location'] is False
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('changes', [dict(fs=0), dict(freq=0), dict(fs=np.inf),
    dict(sample_bound=-1), dict(sample_bound=np.nan), dict(sample_bound=False),
    dict(fs=1e308, freq=1e-308), dict(fs=1e-320, freq=1e-322),
    dict(fs=1e308, freq=1e308, half_cycle=True), dict(uniform_grid=False), dict(uniform_grid='yes'),
    dict(tau=-1), dict(tau=np.nan), dict(half_cycle='yes')])
def test_unsupported_kernel_assumptions_cannot_create_bound(changes):
    values = dict(fs=3500, freq=48, sample_bound=.1, uniform_grid=True)
    values.update(changes)
    out = budget().dft_noise_radius(**values)
    assert out['status'] == 'unsupported' and out['authorizes_location'] is False
    json.dumps(out, allow_nan=False)
