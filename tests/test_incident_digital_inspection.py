"""Digital cursor supports preserve binary samples, gaps and assertion uncertainty."""
import copy
import json

import pytest

from dranalyser.workbench.incident_report_digital import attach_digital_inspection, MAX_CHANNELS, MAX_SEGMENTS
from dranalyser.workbench.incident_report import build_incident_report
from tests.test_incident_reader_model import captures as captures, revision, saved_inputs


def fixture(states, *, times=None, bounds=None, asserted=None, breaks=()):
    times = times if times is not None else [i*.01 for i in range(len(states))]
    source = dict(axis={'elapsed_s': times}, digital=[dict(key='D1', label='Trip', states=states)],
                  header_inventory=[dict(id='D1', normal_state='0')])
    report = dict(digital={}, region_support={'fault': {'indices': bounds or [0, len(states)]}})
    original = copy.deepcopy(source)
    attach_digital_inspection(report, source, {}, {}, {} if asserted is None else {'D1': asserted}, breaks=breaks)
    assert source == original
    json.dumps(report, allow_nan=False)
    return report, source


def test_native_states_have_inclusive_supports_but_no_bridge_over_transition_brackets():
    report, _ = fixture([0, 0, 1, 1, 0], asserted=1)
    row = report['digital']['inspection']['channels'][0]
    assert row['segments'] == [
        dict(from_index=0, to_index=1, from_s=0., to_s=.01, state=0),
        dict(from_index=2, to_index=3, from_s=.02, to_s=.03, state=1),
        dict(from_index=4, to_index=4, from_s=.04, to_s=.04, state=0)]
    summary = row['window_summary']
    assert summary['raw_state_at_start'] == 0 and summary['asserted_at_start'] is False
    assert summary['active_during_window'] is True
    assert summary['observed_active_span_s'] == pytest.approx(.01)
    assert summary['duration_bounds_s'] == pytest.approx([.01, .03])
    assert not summary['censored_start'] and not summary['censored_end']


def test_active_low_is_respected_without_relabelling_high_as_active():
    report, _ = fixture([1, 0, 0, 1], asserted=0)
    row = report['digital']['inspection']['channels'][0]
    assert row['asserted_state'] == 0
    assert row['window_summary']['active_during_window'] is True
    assert row['window_summary']['observed_active_span_s'] == .01
    assert row['window_summary']['observed_high_span_s'] == 0


def test_unreviewed_assertion_remains_raw_even_with_cfg_normal_zero():
    report, _ = fixture([0, 1, 1, 0])
    row = report['digital']['inspection']['channels'][0]
    assert row['asserted_state'] is None
    summary = row['window_summary']
    assert summary['asserted_at_start'] is None and summary['active_during_window'] is None
    assert summary['observed_active_span_s'] is None and summary['duration_bounds_s'] is None
    assert summary['observed_high_span_s'] == .01 and 'unreviewed' in summary['reason']


def test_known_inactive_and_zero_span_are_real_observations_not_unknown():
    report, _ = fixture([0, 0, 0], asserted=1)
    summary = report['digital']['inspection']['channels'][0]['window_summary']
    assert summary['active_during_window'] is False
    assert summary['observed_active_span_s'] == 0 and summary['duration_bounds_s'] == [0., 0.]


def test_capture_and_window_boundary_activity_is_explicitly_censored():
    report, _ = fixture([1, 1, 1, 1], bounds=[1, 3], asserted=1)
    summary = report['digital']['inspection']['channels'][0]['window_summary']
    assert summary['censored_start'] and summary['censored_end']
    assert summary['observed_active_span_s'] == .01
    assert summary['indices'] == [1, 3] and summary['time_range_s'] == [.01, .02]


def test_declared_gap_splits_even_identical_states_and_limits_duration():
    report, _ = fixture([1, 1, 1, 1], times=[0., .01, .1, .11], asserted=1, breaks=[2])
    row = report['digital']['inspection']['channels'][0]
    assert len(row['segments']) == 2
    assert [segment['to_index'] for segment in row['segments']] == [1, 3]
    assert row['window_summary']['observed_active_span_s'] == pytest.approx(.02)
    assert row['window_summary']['duration_bounds_s'] == pytest.approx([.02, .11])
    assert row['window_summary']['gap_count'] == 1


def test_unknown_samples_never_become_zero_or_contiguous_assertions():
    report, _ = fixture([0, 1, None, 1, 0], asserted=1)
    row = report['digital']['inspection']['channels'][0]
    assert all(not segment['from_index'] <= 2 <= segment['to_index'] for segment in row['segments'])
    assert row['window_summary']['unknown_samples'] == 1
    assert row['window_summary']['observed_active_span_s'] == 0
    assert row['window_summary']['duration_bounds_s'] == [0., .04]
    report, _ = fixture([0, None, 0], asserted=1)
    assert report['digital']['inspection']['channels'][0]['window_summary']['active_during_window'] is None


def test_no_event_retains_cursor_states_without_whole_capture_fault_duration():
    report, source = fixture([0, 1, 1, 0], asserted=1)
    report['region_support'] = {}
    attach_digital_inspection(report, source, {}, {}, {'D1': 1})
    row = report['digital']['inspection']['channels'][0]
    assert row['segments']
    assert row['window_summary']['status'] == 'unavailable'
    assert row['window_summary']['duration_bounds_s'] is None


def test_signal_and_segment_budgets_keep_late_event_support_without_fabricating_runs():
    count = 10000
    times = [i*.001 for i in range(count)]
    source = dict(axis={'elapsed_s': times}, digital=[
        dict(key='D'+str(i+1), label='Trip' if i == 5 else 'Unknown '+str(i), states=[j % 2 for j in range(count)])
        for i in range(8)])
    report = dict(digital={}, region_support={'fault': {'indices': [9950, 9990]}})
    attach_digital_inspection(report, source, {}, {}, {})
    inspection = report['digital']['inspection']
    assert len(inspection['channels']) == MAX_CHANNELS and inspection['omitted_channels'] == 4
    assert inspection['channels'][0]['id'] == 'D6'
    for row in inspection['channels']:
        assert len(row['segments']) <= MAX_SEGMENTS and row['omitted_segments'] > 0
        assert any(segment['from_index'] == 9970 for segment in row['segments'])
        assert all(segment['from_index'] == segment['to_index'] and
                   segment['state'] == segment['from_index'] % 2 for segment in row['segments'])


def test_invalid_source_time_is_named_unavailable():
    report = dict(digital={}, region_support={})
    attach_digital_inspection(report, {'axis': {'elapsed_s': []}, 'digital': []}, {}, {}, {})
    assert report['digital']['inspection']['status'] == 'unavailable'


def test_canonical_reader_carries_reviewed_states_clock_and_gaps(captures):
    source = captures['one.cfg']
    source['recorded_times'] = dict(start='05/11/2026,09:12:13.123456', trigger='05/11/2026,09:12:13.223456')
    source['axis']['break_indices'] = [160]
    original = copy.deepcopy(source)
    report = build_incident_report('.', revision(), records=['one.cfg'],
        event_inputs=saved_inputs(captures, asserted_states={'D1': 1}))
    recorded = report['sources'][0]
    assert recorded['record_clock']['start_display'] == '05 Nov 2026 09:12:13.123456'
    assert recorded['record_clock']['timezone_label'] == 'Not declared'
    row = recorded['digital']['inspection']['channels'][0]
    assert row['asserted_state'] == 1 and row['window_summary']['active_during_window'] is True
    assert row['window_summary']['gap_count'] == 1
    assert all(not segment['from_index'] < 160 <= segment['to_index'] for segment in row['segments'])
    assert source == original and report['location']['km_from_S'] is None
