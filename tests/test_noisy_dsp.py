"""Noise/timing perturbations must travel through real parser and DSP."""
import importlib

import numpy as np
import pytest


def fixture_records(path, **kwargs):
    return importlib.import_module('tests.noisy_dsp_records').records(path, **kwargs)


def evaluated(pair):
    runner = importlib.import_module('scripts.noisy_dsp_validation')
    return runner.evaluate(pair)


@pytest.mark.parametrize('timing', ['declared', 'rounded', 'bounded_jitter'])
def test_actual_clean_timestamp_modes_recover_chainage_without_substituting_phasors(tmp_path, timing):
    pair = fixture_records(tmp_path, timing=timing)
    result = evaluated(pair)
    for mode in ('main', 'stage'):
        assert result[mode]['status'] == 'located', result
        assert result[mode]['error_km'] < .05
    assert all(not r.blocked() for r in pair.values())
    assert pair['R'].fs == pytest.approx(1200, rel=2e-5)


def test_seeded_raw_noise_is_nonzero_at_weak_terminal_and_reproducible(tmp_path):
    clean = fixture_records(tmp_path/'clean', profile='weak_R_100')
    noisy = fixture_records(tmp_path/'a', profile='weak_R_100', noise=.01)
    again = fixture_records(tmp_path/'b', profile='weak_R_100', noise=.01)
    different = fixture_records(tmp_path/'c', profile='weak_R_100', noise=.01, seed=855)
    for end in ('S', 'R'):
        for kind in ('V', 'I'):
            ref = max(np.sqrt(np.mean(r.analog[kind+p]**2)) for r in clean.values() for p in 'ABC')
            delta = noisy[end].analog[kind+'A']-clean[end].analog[kind+'A']
            assert .85*.01*ref < np.std(delta) < 1.15*.01*ref
        assert noisy[end].content_hash == again[end].content_hash
        np.testing.assert_array_equal(noisy[end].analog['IA'], again[end].analog['IA'])
        assert not np.array_equal(noisy[end].analog['IA'], different[end].analog['IA'])


def test_metadata_clock_skew_does_not_change_local_dsp_or_promote_e4(tmp_path):
    normal = fixture_records(tmp_path/'normal', noise=.001)
    shifted = fixture_records(tmp_path/'shifted', noise=.001, timing='clock_skew')
    from dranalyser.dsp.clock_quality import clock_quality
    assert (shifted['R'].start_time-normal['R'].start_time).total_seconds() == 1418
    assert shifted['R'].trigger_offset_s() == normal['R'].trigger_offset_s()
    for end in ('S', 'R'):
        np.testing.assert_array_equal(normal[end].analog['IA'], shifted[end].analog['IA'])
        assert not clock_quality(shifted[end])['alignment_eligible']
    a, b = evaluated(normal), evaluated(shifted)
    for mode in ('main', 'stage'):
        assert a[mode] == b[mode]
        assert not b[mode]['clock_shift_applied'] and not b[mode]['method'].startswith('E4')


def test_gap_blocks_both_actual_guarded_workflows(tmp_path):
    pair = fixture_records(tmp_path, timing='gap')
    assert pair['R'].blocked() and 'TIME-DAT' in pair['R'].flag_codes()
    result = evaluated(pair)
    assert all(result[mode]['status'] == 'withheld' for mode in ('main', 'stage'))


def test_balanced_noisy_control_is_reported_without_acceptance_claim(tmp_path):
    result = evaluated(fixture_records(tmp_path, fault='ABC', noise=.001))
    assert all(result[mode]['status'] == 'withheld' for mode in ('main', 'stage'))


def test_weak_noisy_record_without_a_stable_stage_remains_a_counted_refusal(tmp_path):
    result = evaluated(fixture_records(tmp_path, profile='weak_R_100', noise=.01))
    assert result['stage']['status'] == 'withheld'
    assert result['stage']['reason']


def test_noisy_refusals_retain_dsp_quality_evidence(tmp_path):
    result = evaluated(fixture_records(tmp_path, noise=.001))
    assert result['main']['status'] == result['stage']['status'] == 'withheld'
    assert result['quality']['S']['saturation_detected']
    assert result['quality']['S']['saturation_channels']
    assert result['quality']['S']['stage_quality_reasons']
