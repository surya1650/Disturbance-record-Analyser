"""Independent analytic/DFT checks of display-only, one-cycle observations."""
import copy
from dataclasses import FrozenInstanceError
import math

import numpy as np
import pytest

from dranalyser.dsp.cursor_fourier import PreparedTimeline, cursor_fourier
from dranalyser.synth.generator import SynthSpec, generate
from dranalyser.workbench.source_rms import cursor_measurements, sample_rms


def signal(times, magnitude=12., angle=.37, dc=5., frequency=50.):
    return (dc+math.sqrt(2)*magnitude*np.cos(2*np.pi*frequency*np.asarray(times)+angle)).tolist()


def observe(times, values=None, index=-1, frequency=50, **kwargs):
    return cursor_fourier(times, {'a': signal(times) if values is None else values}, frequency,
                          len(times)-1 if index == -1 else index, **kwargs)


def expected(magnitude, angle, time, frequency=50):
    return magnitude*np.exp(1j*(angle+2*np.pi*frequency*time))


def test_uniform_cycle_is_independent_dft_with_dc_and_cursor_phase_reference():
    times = (np.arange(101)/1000).tolist()
    values = signal(times)
    out = observe(times, values, index=63)
    fit = out['channels']['a']
    assert fit['status'] == 'observed'
    window = out['window']
    assert window['start_index'] == 44
    assert window['stop_index'] == 64
    assert window['reference_s'] == times[63]
    local = np.asarray(values[44:64])
    phase = 2*np.pi*50*(np.asarray(times[44:64])-times[63])
    dft = math.sqrt(2)/len(local)*sum(local*np.exp(-1j*phase))
    measured = complex(*fit['phasor'])
    assert measured == pytest.approx(dft, rel=1e-13)
    assert measured == pytest.approx(expected(12, .37, times[63]), rel=1e-13)
    assert fit['rms'] == pytest.approx(12.)
    assert fit['dc'] == pytest.approx(5.)
    assert fit['total_rms'] == pytest.approx(13.)
    assert fit['relative_residual'] < 1e-13
    assert fit['authorizes_location'] is False


@pytest.mark.parametrize('frequency,fs', [(50, 1197), (60, 997)])
@pytest.mark.parametrize('jitter', [False, True])
def test_noninteger_cycle_and_actual_nonuniform_timestamps_recover_known_coefficients(frequency, fs, jitter):
    step = (1+(.1*np.sin(np.arange(100))) if jitter else np.ones(100))/fs
    times = np.cumsum(step).tolist()
    fit = observe(times, signal(times, frequency=frequency), frequency=frequency)['channels']['a']
    assert fit['status'] == 'observed'
    assert complex(*fit['phasor']) == pytest.approx(expected(12, .37, times[-1], frequency), rel=1e-12)
    assert fit['dc'] == pytest.approx(5, rel=1e-12)
    assert fit['relative_residual'] < 1e-12


def test_all_channels_share_support_and_reference_zero_remains_valid_without_angle():
    times = (np.arange(60)/1000).tolist()
    values = {'v': signal(times), 'i': signal(times, 3, -1.1), 'zero': [0.]*60}
    original = copy.deepcopy((times, values))
    out = cursor_fourier(times, values, 50, 40)
    assert out['window']['start_index'] == 21
    assert out['window']['reference_s'] == .04
    for identity, magnitude, angle in [('v', 12, .37), ('i', 3, -1.1)]:
        assert complex(*out['channels'][identity]['phasor']) == pytest.approx(expected(magnitude, angle, .04))
    zero = out['channels']['zero']
    assert zero['status'] == 'observed'
    assert zero['rms'] == zero['total_rms'] == zero['dc'] == zero['relative_residual'] == 0
    assert zero['angle_deg'] is None
    assert (times, values) == original


def test_dc_and_harmonic_total_rms_is_distinct_from_fundamental_without_residual_gate():
    times = (np.arange(101)/1000).tolist()
    values = np.asarray(signal(times))+math.sqrt(2)*4*np.cos(2*np.pi*150*np.asarray(times))
    fit = observe(times, values.tolist())['channels']['a']
    assert fit['rms'] == pytest.approx(12)
    assert fit['total_rms'] == pytest.approx(math.sqrt(144+25+16))
    assert fit['dc'] == pytest.approx(5)
    assert fit['relative_residual'] == pytest.approx(4/math.sqrt(144+16))
    transient = observe(times, [100.]*91+[0.]*10)['channels']['a']
    assert transient['status'] == 'observed'
    assert transient['relative_residual'] > .1
    assert not transient['authorizes_location']


def test_low_residual_cannot_establish_anti_alias_provenance():
    times = (np.arange(101)/1000).tolist()
    # At fs=1000, an unfiltered 950 Hz cosine aliases to 50 Hz. The samples alone
    # cannot distinguish it, so a perfect projection must not certify provenance.
    out = observe(times, signal(times, angle=0, dc=0, frequency=950))
    fit = out['channels']['a']
    assert fit['rms'] == pytest.approx(12)
    assert fit['relative_residual'] < 1e-12
    assert 'anti-alias' in out['basis']
    assert not out['authorizes_location']
    assert not fit['authorizes_location']


def test_incomplete_cycle_missing_samples_and_individual_channel_lengths_are_explicit():
    times = (np.arange(81)/1000).tolist()
    assert observe(times, index=19)['channels']['a']['status'] == 'unavailable'
    assert observe(times, index=20)['channels']['a']['status'] == 'observed'
    values = signal(times)
    values[40] = None
    for index in [40, 59]:
        assert observe(times, values, index=index)['channels']['a']['status'] == 'unavailable'
    assert observe(times, values, index=60)['channels']['a']['status'] == 'observed'
    out = cursor_fourier(times, {'bad': values[:-1], 'valid': signal(times)}, 50, 60)
    assert out['channels']['bad']['status'] == 'unavailable'
    assert out['channels']['valid']['status'] == 'observed'


def test_source_gaps_explicit_join_breaks_and_sparse_phase_sampling_remain_unavailable():
    times = [i*.001+(1. if i >= 50 else 0.) for i in range(100)]
    assert observe(times, index=69)['channels']['a']['status'] == 'unavailable'
    assert observe(times, index=70)['channels']['a']['status'] == 'observed'
    times = (np.arange(100)/1000).tolist()
    assert observe(times, index=69, break_indices=[50])['channels']['a']['status'] == 'unavailable'
    assert observe(times, index=70, break_indices=[50])['channels']['a']['status'] == 'observed'
    sparse = [0., .001, .002, .003, .014, .015, .016, .020]
    assert observe(sparse)['channels']['a']['status'] == 'unavailable'
    too_few = [0., .01, .02, .03]
    assert observe(too_few)['channels']['a']['status'] == 'unavailable'


@pytest.mark.parametrize('frequency', [None, True, np.bool_(True), float('nan'), float('inf'), 0, 39, 71, 10**1000])
def test_unusable_nominal_frequency_never_guesses_a_frequency(frequency):
    times = (np.arange(100)/1000).tolist()
    assert observe(times, frequency=frequency)['channels']['a']['status'] == 'unavailable'


@pytest.mark.parametrize('times', [[], [0., .001, .001], [0., float('nan'), .02], [0., True, .02]])
def test_unknown_or_nonmonotone_times_never_impute_coordinates(times):
    assert observe(times)['channels']['a']['status'] == 'unavailable'


@pytest.mark.parametrize('index', [-1, 1.5, True, 101])
def test_invalid_cursor_index_rejected(index):
    with pytest.raises(ValueError):
        cursor_fourier((np.arange(100)/1000).tolist(), {'a': [1.]*100}, 50, index)


def test_resource_bound_is_explicit_instead_of_unbounded_window_allocation():
    times = (np.arange(6001)/300000).tolist()
    fit = observe(times)['channels']['a']
    assert fit['status'] == 'unavailable'
    assert '4096' in fit['reason']


def test_prepared_timeline_has_identical_checks_is_immutable_and_does_not_rescan_source():
    class Once(list):
        def __iter__(self):
            assert not getattr(self, 'used', False), 'Source timeline iterated twice'
            self.used = True
            return super().__iter__()
    raw = Once(np.arange(100)/1000)
    prepared = PreparedTimeline(raw)
    values = signal(prepared.coordinates)
    for index in (40, 60, 80):
        out = cursor_fourier(prepared, {'a': values}, 50, index)
        assert out['channels']['a']['rms'] == pytest.approx(12.)
    with pytest.raises(FrozenInstanceError):
        prepared.minimum_step_s = 1.
    for invalid in ([], [0., None, .02], [0., .01, .01]):
        out = cursor_fourier(PreparedTimeline(invalid), {'a': [1.]*len(invalid)}, 50, 0)
        assert out['channels']['a']['status'] == 'unavailable'


def test_source_adapter_reuses_prepared_timing_without_global_source_retention():
    source = dict(axis={'elapsed_s': (np.arange(100)/1000).tolist()},
                  nominal_frequency_hz=50, channels=[dict(key='a', values=[10.]*100)])
    cursor_measurements(source, ['a'], 40)
    prepared = source['_cursor_timing'][1]
    cursor_measurements(source, ['a'], 60)
    assert source['_cursor_timing'][1] is prepared


@pytest.mark.parametrize('scale', [1e300, 1e-200])
def test_safe_scaling_of_tiny_and_large_sinusoids_and_constant_dc(scale):
    times = (np.arange(101)/1000).tolist()
    values = signal(times, magnitude=scale, dc=scale/2)
    fit = observe(times, values)['channels']['a']
    assert fit['rms'] == pytest.approx(scale, rel=1e-12, abs=0)
    assert fit['dc'] == pytest.approx(scale/2, rel=1e-12, abs=0)
    assert fit['total_rms'] == pytest.approx(scale*math.sqrt(1.25), rel=1e-12, abs=0)
    constant = observe(times, [scale]*len(times))['channels']['a']
    assert constant['rms'] == 0
    assert constant['dc'] == constant['total_rms'] == scale
    assert constant['angle_deg'] is None


def test_unknown_nonfinite_nonnumeric_values_are_not_zero_filled():
    times = (np.arange(101)/1000).tolist()
    for value in [None, float('nan'), float('inf'), True, '2', 10**1000]:
        values = signal(times)
        values[-1] = value
        assert observe(times, values)['channels']['a']['status'] == 'unavailable'


def test_source_adapter_preserves_labels_units_and_sample_only_unavailability():
    times = (np.arange(101)/1000).tolist()
    channel = dict(key='a', label='VA', units='kV', values=signal(times))
    source = dict(axis={'elapsed_s': times}, nominal_frequency_hz=50, channels=[channel])
    fit = cursor_measurements(source, ['a'], 100)['channels']['a']
    assert (fit['id'], fit['label'], fit['units']) == ('a', 'VA', 'kV')
    assert fit['total_rms'] == pytest.approx(sample_rms(source, channel)['values'][100])
    source['axis']['elapsed_s'] = []
    assert cursor_measurements(source, ['a'], 100)['channels']['a']['status'] == 'unavailable'
    for ids in [[], ['a', 'a'], [['a']], ['unknown'], 'a']:
        with pytest.raises(ValueError):
            cursor_measurements(source, ids, 100)


def test_known_m_synthetic_records_match_independent_dft_on_steady_prefault_samples():
    case = generate(SynthSpec(m=.42, fault='AG', rf=5))
    for record in case.records.values():
        times = record.t.tolist()
        # Trigger index is not used: this selects a complete steady pre-fault support.
        index = next(i for i, t in enumerate(times) if t >= .06)
        channels = {name: record.analog[name].tolist() for name in ('VA', 'VB', 'IA', 'IB')}
        out = cursor_fourier(times, channels, 50, index)
        window = out['window']
        lo, hi = window['start_index'], window['stop_index']
        assert (hi-lo)*(times[1]-times[0]) == pytest.approx(.02)
        for name, values in channels.items():
            phase = 2*np.pi*50*(np.asarray(times[lo:hi])-times[index])
            oracle = math.sqrt(2)/(hi-lo)*sum(np.asarray(values[lo:hi])*np.exp(-1j*phase))
            assert complex(*out['channels'][name]['phasor']) == pytest.approx(oracle, rel=1e-11)
            assert out['channels'][name]['authorizes_location'] is False
