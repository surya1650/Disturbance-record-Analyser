"""Physical truth and independent SVD oracles for rounded-cycle fundamentals."""
import numpy as np
import pytest

from dranalyser.dsp.core import sequence, sliding_dft
from dranalyser.dsp.sequence_budget import dft_noise_radius


def filtered(values, decay):
    out = np.array(values, dtype=float, copy=True)
    if decay is not None and len(out):
        out[0] *= 1-decay
        out[1:] = values[1:]-decay*values[:-1]
    return out


@pytest.mark.parametrize('fs,freq', [(3500, 48), (3200, 47), (4100, 53), (2600, 52)])
@pytest.mark.parametrize('tau', [None, 0, .02, .08])
@pytest.mark.parametrize('half', [False, True])
@pytest.mark.parametrize('origin', [0, .173])
def test_exact_physical_fundamental_on_every_complete_support(fs, freq, tau, half, origin):
    t = origin+np.arange(400)/fs
    truth = 337-91j
    x = np.sqrt(2)*np.real(truth*np.exp(2j*np.pi*freq*t))
    result = sliding_dft(x, t, fs, freq, half_cycle=half, tau=tau, method='basis')
    n = round(fs/freq)
    n = max(n//2, 2) if half else n
    assert np.all(np.isnan(result[:n-1]))
    np.testing.assert_allclose(result[n-1:], truth, rtol=0, atol=1e-8)


@pytest.mark.parametrize('half', [False, True])
@pytest.mark.parametrize('tau', [None, .02, .08])
def test_arbitrary_waveform_matches_independent_filtered_design_svd(half, tau):
    fs, freq = 3500, 48
    t = .113+np.arange(300)/fs
    n = round(fs/freq)
    n = max(n//2, 2) if half else n
    decay = np.exp(-1/fs/tau) if tau is not None else None
    x = np.random.default_rng(2754).normal(size=len(t))*1000
    design = filtered(np.column_stack([np.cos(2*np.pi*freq*t), np.sin(2*np.pi*freq*t)]), decay)
    y = filtered(x, decay)
    result = sliding_dft(x, t, fs, freq, half_cycle=half, tau=tau, method='basis')
    for end in (n-1, n, 2*n+3, len(t)-1):
        coefficients = np.linalg.lstsq(design[end-n+1:end+1], y[end-n+1:end+1], rcond=None)[0]
        truth = (coefficients[0]-1j*coefficients[1])/np.sqrt(2)
        assert result[end] == pytest.approx(truth, abs=1e-8)


@pytest.mark.parametrize('i2', [0, .1, 10])
def test_strong_positive_sequence_does_not_create_negative_sequence(i2):
    fs, freq = 3500, 48
    t = np.arange(500)/fs
    a = np.exp(2j*np.pi/3)
    truth = np.array([1000+i2, 1000*a*a+i2*a, 1000*a+i2*a*a])
    ph = [sliding_dft(np.sqrt(2)*np.real(z*np.exp(2j*np.pi*freq*t)), t, fs, freq, tau=.08, method='basis') for z in truth]
    negative = sequence(*ph)[2]
    np.testing.assert_allclose(negative[round(fs/freq)-1:], i2, rtol=0, atol=1e-8)


@pytest.mark.parametrize('tau', [None, .02])
def test_singular_nyquist_support_is_unavailable(tau):
    t = np.arange(20)/100
    result = sliding_dft(np.ones(20), t, 100, 50, tau=tau, method='basis')
    assert np.all(np.isnan(result))
    assert dft_noise_radius(100, 50, .1, tau=tau, uniform_grid=True, method='basis')['status'] == 'unsupported'


@pytest.mark.parametrize('tau', [None, .02])
def test_short_empty_and_zero_energy_inputs(tau):
    for count in (0, 10, 200):
        t = np.arange(count)/3500
        result = sliding_dft(np.zeros(count), t, 3500, 48, tau=tau, method='basis')
        assert len(result) == count
        assert np.all(np.isnan(result[:72]))
        np.testing.assert_allclose(result[72:], 0, rtol=0, atol=0)


def test_oversized_conditional_kernel_refuses_without_allocating_a_window():
    result = dft_noise_radius(1000000, 1, .1, uniform_grid=True, method='basis')
    assert result['status'] == 'unsupported'


def test_production_default_retains_legacy_phasors():
    fs,freq=3500,48
    t=np.arange(200)/fs
    x=np.sqrt(2)*np.real((1000+10j)*np.exp(2j*np.pi*freq*t))
    n=round(fs/freq)
    legacy=np.sqrt(2)/n*np.sum(x[-n:]*np.exp(-2j*np.pi*freq*t[-n:]))
    assert sliding_dft(x,t,fs,freq)[-1] == pytest.approx(legacy,abs=1e-8)


def test_production_default_retains_known_saturated_abc_refusal():
    from dranalyser import stagea
    rng=np.random.default_rng(0)
    for index in range(9985):
        config=stagea._sample(rng,index)
    result=stagea.run_case(config)
    assert not result.ok, 'Unsafe candidate adoption would locate this saturated ABC case at6.21% error.'
