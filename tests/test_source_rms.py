"""Sample RMS has independent sample arithmetic, not fitted-phasor validity gates."""
import math

import numpy as np
import pytest

from dranalyser.synth.generator import SynthSpec, generate
from dranalyser.workbench.source_rms import sample_rms


def result(values, times=None, frequency=50):
    return sample_rms(dict(axis={'elapsed_s': times if times is not None else [i*.001 for i in range(len(values))]},
                           nominal_frequency_hz=frequency), {'values': values})


def test_one_cycle_sinusoid_dc_and_harmonics_have_known_sample_rms():
    t = np.arange(200)/1000
    values = 3+10*np.sqrt(2)*np.sin(2*np.pi*50*t)+4*np.sqrt(2)*np.cos(2*np.pi*150*t)
    out = result(values.tolist())
    assert out['values'][:20] == [None]*20
    assert out['values'][20:] == pytest.approx([math.sqrt(125)]*180, rel=1e-12)
    assert out['window_s'] == .02


def test_clearing_is_visible_even_when_a_stationary_phasor_would_be_withheld():
    values = [100.]*60+[0.]*60
    rms = result(values)['values']
    assert rms[59] == 100
    assert rms[60] == pytest.approx(100*math.sqrt(19/20))
    assert rms[78] == pytest.approx(100/math.sqrt(20))
    assert rms[79:] == [0.]*41


def test_unknown_samples_and_time_gaps_withhold_only_affected_supports():
    values = [10.]*100
    values[30] = None
    rms = result(values)['values']
    assert rms[29] == 10
    assert rms[30:50] == [None]*20
    assert rms[50] == 10
    times = [i*.001+(1 if i >= 50 else 0) for i in range(100)]
    rms = result([10.]*100, times)['values']
    assert rms[50:70] == [None]*20
    assert rms[70] == 10


def test_nonuniform_source_coordinates_use_stated_equal_sample_weights():
    times = np.cumsum([.0008, .001, .0012]*40).tolist()
    values = [math.sin(i)*20 for i in range(len(times))]
    rms = result(values, times)['values']
    for i in (30, 60, 100):
        window = [v for t, v in zip(times, values, strict=True) if times[i]-.02+1e-12 < t <= times[i]]
        assert rms[i] == pytest.approx(math.sqrt(sum(v*v for v in window)/len(window)), rel=1e-12)


def test_large_small_and_zero_values_do_not_overflow_or_cancel_on_removal():
    values = [1e300]*40+[1e-200]*40+[0.]*40
    rms = result(values)['values']
    assert rms[39] == pytest.approx(1e300)
    assert rms[59] == pytest.approx(1e-200, rel=1e-12, abs=0)
    assert rms[99] == 0
    assert all(v is None or math.isfinite(v) for v in rms)


def test_missing_invalid_time_or_frequency_never_fabricates_rms():
    for times, frequency in (([], 50), ([0, .001, .001], 50), ([0, .001, .002], None),
                             ([0, .001, .002], True), ([0, .001, .002], 0)):
        assert result([1., 2., 3.], times, frequency)['values'] == [None]*3


def test_synthetic_oracle_records_match_independent_direct_window_arithmetic():
    case = generate(SynthSpec(m=.42, fault='AG', rf=5))
    for record in case.records.values():
        times = record.t.tolist()
        for name in ('VA', 'IA'):
            values = record.analog[name].tolist()
            rms = result(values, times)['values']
            for i in range(50, len(times), 23):
                window = [v for t, v in zip(times, values, strict=True) if times[i]-.02+1e-12 < t <= times[i]]
                expected = math.hypot(*window)/math.sqrt(len(window))
                assert rms[i] == pytest.approx(expected, rel=1e-12)
