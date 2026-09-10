"""Independent piecewise sinusoidal current states; no locator or synth helper.

These fixtures validate observation contracts, not multi-stage network physics.
"""
import copy
import datetime as dt
import json

import numpy as np
import pytest

from dranalyser.dsp.pipeline import analyse
from dranalyser.report.evidence import render_evidence
from dranalyser.rules.evidence import relay_evidence
from dranalyser.rules.operation_compare import compare_operations
from dranalyser.rules.stages import compare_stages
from dranalyser.signals import Record


def staged_waveform(fs=1000, shift=0, clock=0, reclose=True):
    t = np.arange(round((.8+shift)*fs))/fs
    u = t-shift
    analog = {}
    for phase, angle in zip('ABC', (0, -2*np.pi/3, 2*np.pi/3), strict=True):
        # A rise, AB evolution, quiet gap, and A again. The true envelope
        # changes are independently specified at .12/.28/.40/.60 seconds.
        active = ((u >= .12) & (u < .40)) | (u >= .60) if phase == 'A' else (
            (u >= .28) & (u < .40) if phase == 'B' else np.zeros(t.size, bool))
        carrier = np.sqrt(2)*np.sin(2*np.pi*50*u+angle)
        analog['I'+phase] = carrier*np.where(active, 110, 10)
        analog['V'+phase] = carrier*np.where(active, 30, 100)
    start = dt.datetime(2026, 1, 1)+dt.timedelta(seconds=clock)
    digital = {'TRIP': (((u >= .36) & (u < .42)) | (u >= .72)).astype(int)}
    if reclose:
        digital['AR CLOSE'] = ((u >= .59) & (u < .64)).astype(int)
    return Record('staged', 'SYNTHETIC', 'relay', '2013', start,
                  start+dt.timedelta(seconds=.15+shift), fs, 50, t, analog, digital,
                  content_hash=('a' if shift == 0 else 'b')*64)


def evidence(fs=1000, shift=0, clock=0, reclose=True):
    an = analyse(staged_waveform(fs, shift, clock, reclose))
    return an, relay_evidence(an, 'left.cfg' if shift == 0 else 'right.cfg', 'S',
                             protection_system='Main-1' if shift == 0 else 'Main-2')


@pytest.mark.parametrize('fs', [1000, 1200, 2400])
def test_evolving_and_reclose_observations_preserve_distinct_local_intervals(fs):
    an, row = evidence(fs)
    stages = row['stages']
    assert stages['status'] == 'observed', stages
    active = [s for s in stages['intervals'] if s['stable'] and s['phase_pattern']]
    assert [s['phase_pattern'] for s in active] == ['A', 'AB', 'A'], stages
    assert [s['kind'] for s in active] == ['initial candidate', 'evolving candidate', 'reclose candidate']
    assert active[-1]['reclose_evidence'][0]['channel'] == 'AR CLOSE'
    for expected, stage in zip((.12, .28, .60), active, strict=True):
        lo, hi = stage['start_boundary_range_s']
        assert lo <= expected <= hi, (expected, stage)
        assert stage['start_s'] == an.record.t[stage['sample_start']]
        assert not stage['eligible_for_estimation']
    assert any(s['kind'] == 'no elevated phase current' for s in stages['intervals'])
    assert stages['intervals'][-1]['continues_at_capture_end']
    assert not stages['applied_to_analysis']
    json.dumps(row, allow_nan=False)


def test_reclose_command_is_required_and_initially_active_command_does_not_prove_new_shot():
    an, row = evidence(reclose=False)
    assert [s for s in row['stages']['intervals'] if s['stable']][-1]['kind'] == 'renewed current candidate'
    an.record.digital['AR CLOSE'] = np.ones(an.record.n, dtype=int)
    row = relay_evidence(an)
    assert [s for s in row['stages']['intervals'] if s['stable']][-1]['kind'] == 'renewed current candidate'
    marker = next(m for m in row['stages']['markers'] if m['signal'] == 'AR_CLOSE')
    assert marker['initially_active'] and marker['intervals'][0]['onset_unknown']


def test_trigger_and_large_clock_offset_do_not_change_local_stage_inventory_or_analysis():
    an, a = evidence()
    arrays = {k: v.copy() for k, v in an.record.analog.items()}
    window, phasors = copy.deepcopy(an.window), copy.deepcopy(an.ps.phasors)
    an.record.start_time += dt.timedelta(seconds=1418)
    an.record.trigger_time += dt.timedelta(seconds=1418.025)
    b = relay_evidence(an)
    assert an.window == window
    for k in arrays:
        np.testing.assert_array_equal(arrays[k], an.record.analog[k])
    for k in phasors:
        np.testing.assert_array_equal(phasors[k], an.ps.phasors[k])
    for left, right in zip(a['stages']['intervals'], b['stages']['intervals'], strict=True):
        assert left['start_s'] == right['start_s']
        assert left['start_boundary_range_s'] == right['start_boundary_range_s']
        assert right['start_trigger_ms'] == pytest.approx(left['start_trigger_ms']-25)
    an.record.trigger_time = None
    assert all(s['start_trigger_ms'] is None for s in relay_evidence(an)['stages']['intervals'])


@pytest.mark.parametrize('problem', ['gap', 'multirate', 'inception', 'baseline', 'missing phase', 'nonfinite'])
def test_unsupported_analog_inventory_keeps_digital_observations(problem):
    an, _ = evidence()
    if problem == 'gap':
        an.record.t[500:] += .05
    elif problem == 'multirate':
        an.record.nrates = 2
    elif problem == 'inception':
        an.inception = None
    elif problem == 'baseline':
        an.inception.t_refined = .01
    elif problem == 'missing phase':
        del an.ps.phasors['IC']
    else:
        an.ref['IC'] = complex(np.nan, 0)
    row = relay_evidence(an)
    assert row['stages']['status'] == 'unavailable'
    assert row['stages']['markers']


def clean_pair():
    # Piecewise transitions can trigger the existing whole-window saturation
    # screen. Test candidate combinatorics separately with explicit clean flags;
    # another test exercises quality refusal with those flags present.
    rows = [evidence()[1], evidence(1200, .04, 1418)[1]]
    for r in rows:
        r['stages']['quality_reasons'] = []
    return rows


def test_repeated_pattern_stays_ambiguous_at_unequal_rates_without_ordinal_pairing():
    rows = clean_pair()
    out = compare_stages(*rows, {'status': 'candidate'})
    assert len(out['pairs']) == 9
    ambiguous = [p for p in out['pairs'] if p['status'] == 'ambiguous']
    assert len(ambiguous) == 4
    assert not out['confirmed'] and not out['applied']
    assert not any(p['confirmed'] for p in out['pairs'])
    assert not any(p['status'] == 'candidate' for p in out['pairs'])


@pytest.mark.parametrize('problem', ['hash', 'stale hash', 'mapping', 'quality', 'identity'])
def test_provenance_and_quality_refusals(problem):
    rows = clean_pair()
    if problem == 'hash':
        rows[1]['record_hash'] = ''
    elif problem == 'stale hash':
        rows[1]['record_hash'] = 'c'*64
    elif problem == 'mapping':
        rows[1]['channel_mapping'] = {'reason': 'new mapping'}
    elif problem == 'quality':
        rows[1]['stages']['quality_reasons'] = ['clipped input']
        for stage in rows[1]['stages']['intervals']:
            stage['estimation_window']['status'] = 'withheld'
    else:
        rows[1]['protection_system'] = 'unknown'
    out = compare_stages(*rows, {'status': 'candidate'})
    assert out['status'] == 'unavailable' and not out['pairs']


def test_single_initial_stage_needs_shape_candidate_and_never_confirms_identity():
    rows = clean_pair()
    for row in rows:
        row['stages']['intervals'] = row['stages']['intervals'][:1]
    out = compare_stages(*rows, {'status': 'ambiguous'})
    assert out['pairs'][0]['status'] == 'review required'
    out = compare_stages(*rows, {'status': 'candidate'})
    assert out['pairs'][0]['status'] == 'candidate' and not out['confirmed']
    rows[1]['end'] = 'R'
    assert compare_stages(*rows, {'status': 'candidate'})['pairs'][0]['status'] == 'candidate'


def test_report_escapes_source_labels_and_pair_order_is_same_terminal_first():
    rows = clean_pair()
    remote = copy.deepcopy(rows[0])
    remote.update(file='remote.cfg', end='R')
    pairs = compare_operations(rows+[remote])
    assert pairs[0]['scope'] == 'same terminal'
    rows[0]['clock_quality']['raw']['local_code'] = '<script>unsafe</script>'
    html = render_evidence(rows, [], pairs)
    assert 'Fault-stage observation intervals' in html and 'Clock-quality evidence' in html
    assert '&lt;script&gt;unsafe&lt;/script&gt;' in html
    assert '<script>unsafe' not in html
