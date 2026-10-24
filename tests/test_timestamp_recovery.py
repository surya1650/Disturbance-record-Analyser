"""Public COMTRADE parsing must not launder invalid acquisition timing."""
import hashlib

import numpy as np
import pytest

from dranalyser.comtrade.parser import read_comtrade
from dranalyser.dsp.clock_quality import clock_quality


def write_timing(directory, stamps, *, nrates=0, timemult=1, numbers=None):
    directory.mkdir(parents=True, exist_ok=True)
    n = len(stamps)
    channels = [f'{i},{name},{name[-1]},,{"A" if name[0] == "I" else "V"},1,0,0,-1e9,1e9,1,1,P'
                for i, name in enumerate(('VA', 'VB', 'VC', 'IA', 'IB', 'IC'), 1)]
    cfg = ['Synthetic,Timing,2013', '6,6A,0D', *channels, '50', str(nrates)]
    cfg.append(f'{1200 if nrates else 0},{n}')
    cfg += ['24/10/2026,00:00:00.000000', '24/10/2026,00:00:00.040000', 'ASCII', str(timemult),
            '0,+5h30', '4,0']
    path = directory/'timing.cfg'
    path.write_text('\n'.join(cfg)+'\n', encoding='ascii')
    numbers = np.arange(1, n+1) if numbers is None else numbers
    path.with_suffix('.dat').write_text(''.join(f'{i},{ts},1,2,3,4,5,6\n' for i, ts in zip(numbers, stamps, strict=True)), encoding='ascii')
    return read_comtrade(str(path))


@pytest.mark.parametrize('fs', [1200, 1200.5, 2400])
@pytest.mark.parametrize('timemult', [.1, 1, 10])
def test_rounded_nonunity_timestamp_scale_recovers_rate_with_explicit_provenance(tmp_path, fs, timemult):
    stamps = np.round(np.arange(1000)/fs*1e6/timemult)
    rec = write_timing(tmp_path, stamps, timemult=timemult)
    assert not rec.blocked()
    assert rec.fs == pytest.approx(fs, rel=2e-6)
    assert rec.t[0] == 0
    assert np.max(abs(rec.t-np.arange(1000)/fs)) < 2e-6
    info = rec.notes['timestamp_recovery']
    assert info['status'] == 'recovered' and info['method'] == 'DAT centered linear fit'
    assert info['maximum_residual_s'] <= .1/rec.fs
    assert not clock_quality(rec)['alignment_eligible']


@pytest.mark.parametrize('problem', ['duplicate', 'reset', 'gap', 'constant', 'descending', 'nan', 'inf'])
def test_invalid_dat_times_cannot_become_a_trusted_uniform_acquisition(tmp_path, problem):
    stamps = np.arange(100)*1000.
    if problem == 'duplicate':
        stamps[50] = stamps[49]
    elif problem == 'reset':
        stamps[50:] -= stamps[50]
    elif problem == 'gap':
        stamps[50:] += 10000
    elif problem == 'constant':
        stamps[:] = 0
    elif problem == 'descending':
        stamps = stamps[::-1]
    else:
        stamps[50] = float(problem)
    rec = write_timing(tmp_path, stamps)
    assert rec.blocked(), 'Parser silently regularized invalid DAT timing'
    assert any(f.code == 'TIME-DAT' and f.severity == 'block' for f in rec.flags)
    assert rec.notes['timestamp_recovery']['status'] == 'invalid'
    assert np.all(np.isfinite(rec.t)) and np.isfinite(rec.fs) and rec.fs > 0


@pytest.mark.parametrize('problem', ['missing', 'duplicate', 'fractional', 'nan'])
def test_bad_sample_numbers_are_not_hidden_even_with_a_declared_rate(tmp_path, problem):
    numbers = np.arange(1, 101, dtype=float)
    if problem == 'missing':
        numbers[50:] += 1
    elif problem == 'duplicate':
        numbers[50] = numbers[49]
    elif problem == 'fractional':
        numbers[50] += .5
    else:
        numbers[50] = np.nan
    rec = write_timing(tmp_path, np.zeros(100), nrates=1, numbers=numbers)
    assert rec.blocked()
    assert 'TIME-SAMPLE' in rec.flag_codes()


def test_declared_rate_remains_authoritative_for_zero_dat_stamps(tmp_path):
    rec = write_timing(tmp_path, np.zeros(100), nrates=1)
    assert not rec.blocked() and rec.fs == 1200
    np.testing.assert_allclose(rec.t, np.arange(100)/1200)
    assert rec.notes['timestamp_recovery']['status'] == 'declared'


def test_bounded_jitter_and_large_origin_preserve_local_time_and_clock_metadata(tmp_path):
    rng = np.random.default_rng(854)
    stamps = 1e12+np.round(np.arange(1000)/1200*1e6+rng.uniform(-5, 5, 1000))
    rec = write_timing(tmp_path, stamps)
    assert not rec.blocked() and rec.fs == pytest.approx(1200, rel=2e-6)
    assert rec.t[0] == 0
    assert rec.notes['tmq_code'] == '4' and rec.notes['local_code'] == '+5h30'
    assert rec.trigger_offset_s() == .04
    expected = hashlib.sha256((tmp_path/'timing.cfg').read_bytes()+(tmp_path/'timing.dat').read_bytes()).hexdigest()
    assert rec.content_hash == expected
    quality = clock_quality(rec)
    assert quality['verified'] is quality['alignment_eligible'] is quality['applied'] is False


def test_too_short_timestamp_only_capture_is_blocked(tmp_path):
    assert write_timing(tmp_path, [0, 833]).blocked()


@pytest.mark.parametrize('timemult', [0, -1, float('nan'), 'invalid'])
def test_invalid_timestamp_multiplier_cannot_be_silently_normalized(tmp_path, timemult):
    import json
    rec = write_timing(tmp_path, np.arange(100)*1000., timemult=timemult)
    assert rec.blocked()
    assert rec.notes['timestamp_recovery']['status'] == 'invalid'
    json.dumps(rec.notes['timestamp_recovery'], allow_nan=False)


@pytest.mark.parametrize('column', ['timestamp', 'sample_number'])
def test_missing_first_ascii_timing_field_is_not_a_genuine_zero(tmp_path, column):
    stamps = list(np.arange(100)*1000.)
    numbers = list(np.arange(100))
    if column == 'timestamp':
        stamps[0] = ''
    else:
        numbers[0] = ''
    rec = write_timing(tmp_path, stamps, numbers=numbers)
    assert rec.blocked()
    assert ('TIME-DAT' if column == 'timestamp' else 'TIME-SAMPLE') in rec.flag_codes()


def test_slow_timestamp_deviation_retains_untrusted_fit_for_inspection_only(tmp_path):
    k = np.arange(3000)
    stamps = k*833.+300*np.sin(2*np.pi*k/len(k))
    rec = write_timing(tmp_path, stamps)
    fitted_period = np.polyfit(k, stamps*1e-6, 1)[0]
    assert rec.blocked() and rec.notes['timestamp_recovery']['status'] == 'invalid'
    assert rec.fs == pytest.approx(1/fitted_period, rel=1e-10)
    assert rec.notes['timestamp_recovery']['display_rate_basis'] == 'untrusted DAT fit; inspection only'
    assert not rec.notes['timestamp_recovery']['alignment_eligible']
