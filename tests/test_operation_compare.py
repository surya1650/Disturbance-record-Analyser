"""Independent onset-shape fixtures and conservative operational comparisons."""
import copy
import datetime as dt

import numpy as np
import pytest

from dranalyser.dsp.correlation import correlate_onsets, onset_profile
from dranalyser.dsp.pipeline import analyse
from dranalyser.report.evidence import render_evidence
from dranalyser.rules.evidence import relay_evidence
from dranalyser.rules.operation_compare import compare_operations
from dranalyser.signals import Record
from tests.test_relay_evidence import analysed


def profile(fs=1000, onset=.12, residual=0, shape='step'):
    t = np.arange(-.1, .2, 1/fs)
    if shape == 'step':
        # Independent continuous onset envelope; two opposite, unequal signals.
        z = (1+np.tanh((t-residual)/.002))/2
    elif shape == 'periodic':
        z = (1+np.cos(2*np.pi*(t-residual)/.005))/2
    elif shape == 'ramp':
        z = t+.1
    else:
        z = np.zeros_like(t)
    return {'t': t, 'onset': onset, 'freq': 50, 'reason': '',
            'channels': {'IA': 10+100*z, 'VA': 100-70*z}}


@pytest.mark.parametrize('residual', [-.002, 0, .002])
def test_unique_shape_candidate_recovers_local_lag_at_unequal_rates(residual):
    left, right = profile(), profile(1200, .16, residual)
    right['channels']['IA'] *= 7  # normalization permits independent infeed magnitudes
    out = correlate_onsets(left, right)
    assert out['status'] == 'candidate', out
    assert out['lag_ms'] == pytest.approx(40+residual*1000, abs=1.01)
    assert out['score'] > .99
    assert out['lag_range_ms'][0] <= out['lag_ms'] <= out['lag_range_ms'][1]
    assert out['grid_ms'] >= 1
    assert out['applied'] is False
    reverse = correlate_onsets(right, left)
    assert reverse['lag_ms'] == pytest.approx(-out['lag_ms'], abs=1.01)


@pytest.mark.parametrize('shape', ['flat', 'periodic', 'ramp'])
def test_unidentifiable_shapes_never_publish_lag(shape):
    out = correlate_onsets(profile(shape=shape), profile(1200, shape=shape))
    assert out['status'] in ('unavailable', 'ambiguous'), out
    assert out['lag_ms'] is None and out['lag_range_ms'] is None


def test_boundary_peak_and_inconsistent_channels_are_withheld():
    edge = correlate_onsets(profile(), profile(residual=.005))
    assert edge['status'] == 'ambiguous' and edge['lag_ms'] is None
    wrong = profile()
    wrong['channels']['VA'] = 110-wrong['channels']['VA']
    out = correlate_onsets(profile(), wrong)
    assert out['status'] == 'inconsistent' and out['lag_ms'] is None


@pytest.mark.parametrize('problem', ['short', 'missing', 'nonfinite', 'frequency'])
def test_bad_profiles_do_not_gain_precision_by_discarding_data(problem):
    right = profile()
    if problem == 'short':
        mask = right['t'] >= -.005
        right['t'] = right['t'][mask]
        right['channels'] = {n: v[mask] for n, v in right['channels'].items()}
    elif problem == 'missing':
        del right['channels']['VA']
    elif problem == 'nonfinite':
        right['channels']['VA'][:] = np.nan
    else:
        right['freq'] = 60
    out = correlate_onsets(profile(), right)
    assert out['status'] == 'unavailable' and out['lag_ms'] is None


def analysis_for_profile():
    an = analysed()
    an.freq = 50
    an.ref = {n: 10+0j for n in ('IA', 'IB', 'IC')}
    an.ps.t = an.record.t
    an.ps.valid_from = 0
    z = (an.ps.t >= .02).astype(float)
    an.ps.phasors = {'IA': (10+100*z).astype(complex), 'VA': (100-70*z).astype(complex),
                     'IB': np.full(200, 10+0j), 'IC': np.full(200, 10+0j)}
    return an


@pytest.mark.parametrize('problem', ['no inception', 'saturated', 'clipped', 'multirate', 'gap', 'evolving'])
def test_profile_quality_and_changing_phase_pattern_force_local_fallback(problem):
    an = analysis_for_profile()
    if problem == 'no inception':
        an.inception = None
    elif problem == 'saturated':
        an.saturation.detected = True
    elif problem == 'clipped':
        an.clipping = ['IA']
    elif problem == 'multirate':
        an.record.nrates = 2
    elif problem == 'gap':
        an.record.t[90:] += .01
    else:
        an.ps.phasors['IB'][100:] = 110+0j
    out = correlate_onsets(onset_profile(an), profile())
    assert out['status'] == 'unavailable' and out['lag_ms'] is None


def records():
    a = analysed(digital={'Any Trip': (np.arange(200) >= 60).astype(int)})
    b = analysed(trigger=.055, digital={'Any Trip': (np.arange(200) >= 80).astype(int)})
    return [relay_evidence(a, 'a.cfg', 'S', 'primary', protection_system='Main-1'),
            relay_evidence(b, 'b.cfg', 'S', 'corroborating', protection_system='Main-2')]


def test_same_end_compares_local_durations_without_inventing_clock_order():
    pair = compare_operations(records(), {'a.cfg': profile(), 'b.cfg': profile()})[0]
    trip = next(p for p in pair['points'] if p['signal'] == 'TRIP')
    assert trip['left']['first_edge_inception_ms'] == pytest.approx(40)
    assert trip['right']['first_edge_inception_ms'] == pytest.approx(60)
    assert trip['local_duration_difference_ms'] == pytest.approx(20)
    assert pair['association']['applied'] is False
    rows = records()
    rows[1]['end'] = 'R'
    cross = compare_operations(rows, {'a.cfg': profile(), 'b.cfg': profile()})[0]
    assert all(p['local_duration_difference_ms'] is None for p in cross['points'])


def test_unknown_identity_missing_points_and_disagreement_do_not_choose_correct_relay():
    rows = records()
    rows[1]['protection_system'] = 'unknown'
    rows[1]['signals'] = []
    out = compare_operations(rows)[0]
    assert any('identity' in n for n in out['notes'])
    assert all(p['comparison'] == 'not comparable' for p in out['points'])
    assert all(p['local_duration_difference_ms'] is None for p in out['points'])
    rows[1] = relay_evidence(analysed(digital={'Any Trip': np.zeros(200)}), 'b.cfg', 'S')
    out = compare_operations(rows)[0]
    assert out['status'] == 'review differences'
    assert any(p['comparison'] == 'different observations' for p in out['points'])


@pytest.mark.parametrize('problem', ['fault type', 'no fault', 'repeated trip', 'reclose', 'unavailable'])
def test_wrong_or_multiple_stages_cannot_produce_common_timing(problem):
    rows = records()
    if problem == 'fault type':
        rows[1]['fault_type'] = 'BG'
    elif problem == 'no fault':
        rows[0]['fault_type'] = rows[1]['fault_type'] = 'NONE'
    elif problem == 'unavailable':
        rows[1] = dict(rows[1], status='unavailable', reason='bad input')
    elif problem == 'reclose':
        close = next(s for s in rows[1]['signals'] if s['signal'] == 'AR_CLOSE')
        close.update(state='assertion observed',
                     points=[{'channel': 'Reclose', 'assertions_s': [.12], 'initially_active': False}])
    else:
        trip = next(s for s in rows[1]['signals'] if s['signal'] == 'TRIP')
        trip['points'][0]['assertions_s'].append(.15)
    out = compare_operations(rows, {'a.cfg': profile(), 'b.cfg': profile()})[0]
    assert out['association']['status'] != 'candidate'
    assert not out['association']['applied']
    assert all(p['local_duration_difference_ms'] is None for p in out['points'])


def test_pair_results_ignore_primary_and_upload_order_and_escape_report_labels():
    rows = records()
    expected = compare_operations(rows)
    changed = copy.deepcopy(rows[::-1])
    for r in changed:
        r['role'] = 'corroborating' if r['role'] == 'primary' else 'primary'
    assert compare_operations(changed) == expected
    expected[0]['left'] = '<script>alert(1)</script>'
    html = render_evidence(rows, [], expected)
    assert '&lt;script&gt;' in html and '<script>alert(1)' not in html
    assert 'Operation comparisons and onset association' in html


def waveform(fs, onset, clock_offset):
    t = np.arange(int(.4*fs))/fs
    fault = t >= onset
    analog = {}
    for phase, angle in zip('ABC', (0, -2*np.pi/3, 2*np.pi/3), strict=True):
        carrier = np.sqrt(2)*np.sin(2*np.pi*50*(t-onset)+angle)
        analog['I'+phase] = carrier*(np.where(fault, 110, 10) if phase == 'A' else 10)
        analog['V'+phase] = carrier*(np.where(fault, 30, 100) if phase == 'A' else 100)
    start = dt.datetime(2026, 1, 1)+dt.timedelta(seconds=clock_offset)
    return Record('waveform', 'synthetic', 'relay', '1999', start,
                  start+dt.timedelta(seconds=onset+.015), fs, 50, t, analog,
                  {'Any Trip': (t >= onset+.12).astype(int)})


def test_actual_dsp_on_analytic_waveforms_ignores_large_free_running_clock_offset():
    a, b = analyse(waveform(1000, .12, 0)), analyse(waveform(1200, .16, 1418))
    out = correlate_onsets(onset_profile(a), onset_profile(b))
    assert out['status'] == 'candidate', out
    assert out['lag_ms'] == pytest.approx(40, abs=2)
    # Clock metadata is neither used to recover this local-coordinate shift nor changed.
    assert (b.record.start_time-a.record.start_time).total_seconds() == 1418
    assert not out['applied']
    b.record.trigger_time = None
    b.record.start_time = None
    assert correlate_onsets(onset_profile(a), onset_profile(b)) == out
