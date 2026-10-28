"""Recording viewer timing and digital display facts do not invent observations."""
import json

import pytest

from dranalyser.workbench.source_display import digital_activity, timeline


def test_trigger_relative_axis_keeps_exact_nonuniform_ticks_and_midnight():
    source = dict(axis={'elapsed_s': [0, .0008, .0017, .0026]}, recorded_times={
        'start': '31/12/2025,23:59:59.999000', 'trigger': '01/01/2026,00:00:00.001000'})
    result = timeline(source)
    assert result['trigger_offset_s'] == pytest.approx(.002)
    assert result['trigger_index'] == pytest.approx(2+1/3)
    assert result['ticks'] == [[0, 0], [1, .0008], [2, .0017], [3, .0026]]
    assert result['start_local'] == '2025-12-31T23:59:59.999000'
    assert result['trigger_local'] == '2026-01-01T00:00:00.001000'
    json.dumps(result, allow_nan=False)


def test_unavailable_time_and_outside_record_trigger_are_explicit():
    source = dict(axis={'elapsed_s': []}, recorded_times={'start': 'invalid', 'trigger': None})
    assert timeline(source)['trigger_offset_s'] is None
    assert timeline(source)['ticks'] == []
    source.update(axis={'elapsed_s': [0, .001, .002]}, recorded_times={
        'start': '01/01/2026,00:00:00', 'trigger': '01/01/2026,00:00:01'})
    assert timeline(source)['trigger_index'] is None


def test_axis_payload_is_bounded_and_includes_exact_endpoints():
    times = [i*.0008 for i in range(10000)]
    result = timeline(dict(axis={'elapsed_s': times}))
    assert len(result['ticks']) <= 513
    assert result['ticks'][0] == [0, times[0]]
    assert result['ticks'][-1] == [9999, times[-1]]


def test_high_spans_unknown_gaps_and_capture_boundaries_remain_distinct():
    states = [1, 1, 0, None, 1, 1, 0, 1]
    activity = digital_activity(states, [i*.001 for i in range(len(states))])
    assert activity['transition_count'] == 3
    assert activity['high_samples'] == 5 and activity['unknown_samples'] == 1
    first, middle, last = activity['high_intervals']
    assert first['start_open'] and not first['end_open']
    assert middle['start_open'] and not middle['end_open']
    assert not last['start_open'] and last['end_open']
    assert first['observed_span_s'] == pytest.approx(.001)
    assert last['observed_span_s'] == 0
    limited = digital_activity(states, [], limit=1)
    assert len(limited['high_intervals']) == 1 and limited['omitted_intervals'] == 2
    assert limited['high_intervals'][0]['observed_span_s'] is None


def test_constant_and_unknown_digital_channels_do_not_claim_transitions():
    for states in ([0]*4, [1]*4, [None]*4, [0, None, 1, None]):
        assert digital_activity(states, [])['transition_count'] == 0
