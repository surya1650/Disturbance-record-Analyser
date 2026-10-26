"""Independent CT circuit equations, not a production synthesis oracle."""
import numpy as np
import pytest

from tests.ct_quality_oracle import excitation, simulate


def test_linear_limit_matches_analytic_sinusoidal_response():
    fs, f, resistance, inductance = 19200, 50, .2, 10
    t = np.arange(9600)/fs
    u = np.sqrt(2)*np.sin(2*np.pi*f*t)
    # Steady-state secondary-referred flux: R/(R/L+jw) * U.
    flux_ph = resistance/(resistance/inductance+2j*np.pi*f)*(-1j*np.sqrt(2))
    result = simulate(u, fs, burden=resistance, initial_flux=flux_ph.real)
    expected_flux = np.real(flux_ph*np.exp(2j*np.pi*f*t))
    assert np.max(abs(result['flux']-expected_flux)) < 2e-7
    assert np.max(abs(result['secondary']-(u-expected_flux/inductance))) < 2e-8


def test_balance_knee_and_trapezoidal_volt_seconds():
    fs = 2400
    t = np.arange(720)/fs
    u = np.sqrt(2)*np.sin(2*np.pi*50*t)+1.4*np.exp(-t/.065)
    result = simulate(u, fs, burden=1.6, initial_flux=.4*.03, substeps=1)
    assert np.max(abs(result['flux'])) > .03
    assert np.max(abs(result['secondary']+result['excitation']-u)) < 1e-12
    assert np.allclose(np.diff(result['flux']), 1.6/(2*fs)*(result['secondary'][1:]+result['secondary'][:-1]), atol=1e-13)
    assert np.all(result['flux']*result['excitation'] >= 0)


def test_odd_symmetry_continuity_and_numerical_convergence():
    assert excitation(.03) == pytest.approx(.003)
    assert excitation(.03+1e-12) == pytest.approx(.003, abs=3e-9)
    t = np.arange(720)/2400
    u = 2*np.sin(2*np.pi*50*t)+np.exp(-t/.04)
    a = simulate(u, 2400, burden=2, initial_flux=.021, substeps=16)
    b = simulate(-u, 2400, burden=2, initial_flux=-.021, substeps=16)
    assert np.allclose(a['secondary'], -b['secondary'], atol=1e-12)
    finer = simulate(u, 2400, burden=2, initial_flux=.021, substeps=64)
    assert np.sqrt(np.mean((a['secondary']-finer['secondary'])**2)) < .003


@pytest.mark.parametrize('change', [dict(fs=0), dict(fs=np.inf), dict(burden=-1),
    dict(initial_flux=np.nan), dict(substeps=0), dict(substeps=1.2), dict(primary=[1, np.nan]),
    dict(primary=[]), dict(primary=[[1, 2]])])
def test_invalid_parameters_are_explicit_errors(change):
    values = dict(primary=np.ones(20), fs=2400, burden=1)
    values.update(change)
    with pytest.raises(ValueError):
        simulate(**values)

