"""Independent phase signals -> secondary ADC integers -> public COMTRADE."""
import importlib

import numpy as np
import pytest


def builder():
    return importlib.import_module('tests.full_record_acquisition')


def test_primary_secondary_adc_roundtrip_and_digital_chronology(tmp_path):
    pair, truth = builder().records(tmp_path, split='development', profile='baseline', fault='AG', scenario='clean')
    for end, rec in pair.items():
        assert set(rec.analog) == set(('IA', 'IB', 'IC', 'VA', 'VB', 'VC'))
        assert not rec.blocked() and rec.nrates == 1
        for name, target in truth[end]['ideal'].items():
            meta = rec.analog_meta[name]
            ratio = 1000 if name[0] == 'I' else 2000
            assert meta.normalised and meta.ps == 'S' and meta.primary/meta.secondary == ratio
            np.testing.assert_allclose(rec.analog[name]/ratio, target, atol=meta.a*.501)
            assert np.array_equal(rec.raw_analog[name], np.rint(rec.raw_analog[name]))
        assert rec.first_assert('TRIP') < rec.first_assert('CB_OPEN')
        assert rec.first_assert('PICKUP') < rec.first_assert('TRIP')
        assert truth[end]['window_indices'][1] < np.flatnonzero(rec.digital['CB_OPEN'])[0]


def test_ct_chain_precedes_noise_adc_and_preserves_balance(tmp_path):
    pair, truth = builder().records(tmp_path, split='validation', profile='baseline', fault='AG', scenario='ct_noisy')
    for end, values in truth.items():
        assert values['ct_channels'] == ['IA', 'IB', 'IC']
        assert values['ct_balance_max_residual'] < 1e-10
        assert max(values['ct_peak_flux_knee'].values()) > 1
        assert any(np.max(abs(values['ct_only'][n]-values['ideal'][n])) > .01 for n in values['ct_channels'])
        assert any(np.max(abs(pair[end].analog[n]/1000-values['ct_only'][n])) > .001 for n in values['ct_channels'])


def test_noise_and_new_split_are_deterministic(tmp_path):
    a, truth = builder().records(tmp_path/'a', split='development', profile='baseline', fault='BC', scenario='white_0.01')
    b, _ = builder().records(tmp_path/'b', split='development', profile='baseline', fault='BC', scenario='white_0.01')
    for end in a:
        assert a[end].content_hash == b[end].content_hash
        assert all(np.array_equal(a[end].analog[n], b[end].analog[n]) for n in a[end].analog)
        assert truth[end]['freq_true'] == 49


@pytest.mark.parametrize('scenario,blocked', [('gap', True), ('clock_skew', False), ('rate_error', False)])
def test_acquisition_truth_and_clock_provenance(tmp_path, scenario, blocked):
    pair, truth = builder().records(tmp_path, split='validation', profile='baseline', fault='ABG', scenario=scenario)
    assert pair['R'].blocked() is blocked
    if scenario == 'gap':
        assert 'TIME-DAT' in pair['R'].flag_codes()
    elif scenario == 'clock_skew':
        assert (pair['R'].trigger_time-pair['S'].trigger_time).total_seconds() == 1418
        assert pair['R'].time_basis != 'synchronised'
    else:
        assert pair['R'].fs == pytest.approx(truth['R']['fs_true']*1.005)


@pytest.mark.parametrize('scenario,name', [('clip_i', 'IA'), ('clip_v', 'VA')])
def test_adc_clipping_uses_recorded_rails(tmp_path, scenario, name):
    pair, _ = builder().records(tmp_path, split='development', profile='baseline', fault='AG', scenario=scenario)
    rec = pair['S']
    rails = rec.analog_meta[name]
    assert np.sum(rec.raw_analog[name] >= rails.adc_max) >= 3
    assert np.max(rec.raw_analog[name]) == rails.adc_max


def test_fundamental_alias_is_indistinguishable_after_sampling():
    module = importlib.import_module('tests.full_record_signals')
    values = module.signals('development', 'baseline', 'AG', 'alias_fundamental')['S']
    t = np.arange(len(values['samples']['IA']))/values['fs_true']
    added = values['samples']['IA']-values['ct_only']['IA']
    expected = -.15*values['family_scale']['I']*np.sin(2*np.pi*values['freq_true']*t)
    np.testing.assert_allclose(added, expected, atol=1e-11)


@pytest.mark.parametrize('change', [dict(split='unknown'), dict(profile='unknown'), dict(fault='BAD'), dict(scenario='unknown')])
def test_invalid_configuration_does_not_create_output(tmp_path, change):
    values = dict(split='development', profile='baseline', fault='AG', scenario='clean')
    values.update(change)
    with pytest.raises(ValueError, match='configuration'):
        builder().records(tmp_path/'not-created', **values)
    assert not (tmp_path/'not-created').exists()
