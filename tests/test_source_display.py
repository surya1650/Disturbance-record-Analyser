"""Native activity and relay-local display coordinates must not infer physical timing."""
import copy
import hashlib

import pytest

from dranalyser.workbench.source_display import digital_activity, display_facts, timeline
from dranalyser.workbench.source_inspection import inspection_record
from tests import test_source_inspection as source_fixtures

revision = source_fixtures.revision


def source(times, states, *, recorded=None, breaks=()):
    return {'axis': {'elapsed_s': times}, 'recorded_times': recorded or {},
            'digital': [{'key': 'D1', 'states': states}], 'break_indices': breaks}


def test_trigger_offset_fractional_display_index_and_calendar_rollover():
    record = source([0, .001, .002, .004], [], recorded={
        'start': '31/12/2025,23:59:59.999500', 'trigger': '01/01/2026,00:00:00.001000'})
    facts = timeline(record)
    assert facts['trigger_offset_s'] == .0015
    assert facts['trigger_index'] == 1.5
    assert facts['ticks'] == [[0, 0], [1, .001], [2, .002], [3, .004]]
    assert 'not inferred fault inception' in facts['basis']
    assert facts['start_local'].startswith('2025-12-31T23:59:59')
    assert facts['trigger_local'].startswith('2026-01-01T00:00:00')


def test_nanosecond_fraction_difference_does_not_round_via_datetime_microseconds():
    record = source([0, .001], [], recorded={
        'start': '29/10/2026,01:02:03.123456789', 'trigger': '29/10/2026,01:02:03.123456790'})
    facts = timeline(record)
    assert facts['trigger_offset_s'] == 1e-9
    assert facts['start_local'].endswith('.123456789')
    assert facts['trigger_index'] == pytest.approx(1e-6)


@pytest.mark.parametrize('start,trigger', [('garbage', '01/01/2026,00:00:00'),
    ('01/01/2026,00:00:00', None), ('31/02/2026,00:00:00', '01/03/2026,00:00:00'),
    ('01/01/2026,23:59:60', '02/01/2026,00:00:00'), ('x' * 200, 'y')])
def test_invalid_or_missing_recorded_time_never_invents_trigger(start, trigger):
    facts = timeline(source([0, .001], [], recorded={'start': start, 'trigger': trigger}))
    assert facts['trigger_offset_s'] is facts['trigger_index'] is None


def test_offset_outside_capture_and_sample_only_axes_do_not_get_trigger_index():
    recorded = {'start': '01/01/2026,00:00:00', 'trigger': '01/01/2026,00:00:01'}
    assert timeline(source([0, .1], [], recorded=recorded))['trigger_index'] is None
    facts = timeline(source([], [], recorded=recorded))
    assert facts['trigger_offset_s'] == 1 and facts['ticks'] == []
    assert facts['trigger_index'] is None


def test_ticks_remain_bounded_over_full_sample_limit():
    facts = timeline(source([i / 1000 for i in range(200000)], []))
    assert len(facts['ticks']) <= 513
    assert facts['ticks'][0] == [0, 0]
    assert facts['ticks'][-1] == [199999, 199.999]


def test_activity_exact_edges_unknowns_open_intervals_and_nonuniform_support():
    states = [1, 1, None, 1, 1, 0, 1]
    times = [0, .001, .002, .004, .006, .007, .008]
    facts = digital_activity(states, times)
    assert facts['transition_count'] == 2
    assert facts['first_transition_index'] == 5
    assert (facts['rising_count'], facts['falling_count']) == (1, 1)
    assert facts['high_samples'] == facts['active_samples'] == 5
    assert facts['unknown_samples'] == 1
    assert facts['active_duration_s'] == pytest.approx(.003)
    assert [i['observed_span_s'] for i in facts['high_intervals']] == pytest.approx([.001, .002, 0])
    assert [i['start_open'] for i in facts['high_intervals']] == [True, True, False]
    assert [i['end_open'] for i in facts['high_intervals']] == [True, False, True]
    assert 'not verified assertion polarity' in facts['basis']
    assert 'not zero pulse duration' in facts['basis']


def test_sample_only_high_and_zero_keep_duration_unknown_not_zero():
    for states in ([0, 0], [1, 1], [None, None], []):
        facts = digital_activity(states, [])
        assert facts['active_duration_s'] is None
        assert facts['transition_count'] == 0
        assert all(i['observed_span_s'] is None for i in facts['high_intervals'])
    assert digital_activity([0, 0], [0, .001])['active_duration_s'] == 0


def test_acquisition_gaps_and_explicit_boundaries_do_not_imply_state_edges():
    record = source([0, .001, 1, 1.001], [0, 1, 0, 1])
    facts = display_facts(record)['activities']['D1']
    assert display_facts(record)['break_indices'] == [2]
    assert facts['transition_count'] == 2
    assert facts['falling_count'] == 0
    assert facts['high_intervals'][0]['end_open'] is True
    bounded = digital_activity([1, 1, 1, 1], [0, .001, .002, .003], break_indices=[2])
    assert bounded['active_duration_s'] == pytest.approx(.002)
    assert len(bounded['high_intervals']) == 2
    assert bounded['high_intervals'][0]['end_open'] is True
    assert bounded['high_intervals'][1]['start_open'] is True


def test_discontinuity_metadata_is_bounded_and_omissions_are_explicit():
    record = source([i / 1000 for i in range(1000)], [1] * 1000, breaks=range(1, 1000))
    facts = display_facts(record)
    assert facts['break_indices'] == list(range(1, 513))
    assert facts['omitted_break_indices'] == 487
    assert facts['activities']['D1']['active_duration_s'] == 0


def test_detail_budget_does_not_hide_exact_activity_counts():
    n = 15625
    record = source([i / 1000 for i in range(n)], [i % 2 for i in range(n)])
    record['digital'] = [{'key': f'D{i + 1}', 'states': record['digital'][0]['states']} for i in range(256)]
    facts = display_facts(record)
    assert sum(len(v['high_intervals']) for v in facts['activities'].values()) == 512
    assert all(v['transition_count'] == n - 1 for v in facts['activities'].values())
    assert facts['activities']['D256']['high_intervals'] == []
    assert facts['activities']['D256']['omitted_intervals'] == n // 2


def test_inspection_response_exposes_exact_activity_and_retains_frozen_revision(revision):
    root, row, _ = revision
    before = copy.deepcopy(row)
    data = inspection_record(root, row, 'event.cfg')
    digital = next(c for c in data['channels'] if c['id'] == 'D1')
    assert digital['activity']['transition_count'] == 1
    assert digital['activity']['unknown_samples'] == 1
    assert data['timeline']['trigger_offset_s'] == 0
    assert row == before
    digital['activity']['transition_count'] = 999
    data['timeline']['ticks'][0][1] = 999
    fresh = inspection_record(root, row, 'event.cfg')
    assert fresh['channels'][-1]['activity']['transition_count'] == 1
    assert fresh['timeline']['ticks'][0][1] == 0


def test_activity_detects_short_pulse_even_when_display_bucket_is_missing(revision):
    root, row, folder = revision
    n = 20000
    cfg = folder / 'event.cfg'
    cfg.write_text(cfg.read_text().replace('0,4', f'0,{n}'))
    dat = folder / 'event.dat'
    dat.write_text('\n'.join(f'{i + 1},{i * 1000},1,2,{"" if i == 7 else 1 if i == 8 else 0}' for i in range(n)) + '\n')
    for entry in row['files']:
        entry['sha256'] = hashlib.sha256((folder / entry['name']).read_bytes()).hexdigest()
    result = inspection_record(root, row, 'event.cfg')
    digital = next(c for c in result['channels'] if c['id'] == 'D1')
    assert digital['activity']['transition_count'] == 1
    assert digital['activity']['high_samples'] == 1
    assert digital['activity']['first_transition_index'] == 9
    assert digital['activity']['active_duration_s'] == 0
    assert not any(point[2] == 1 for point in digital['trace'])
    assert sum(len(c['trace']) for c in result['channels']) <= 16000
