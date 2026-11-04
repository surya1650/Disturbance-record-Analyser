"""Event views retain actual source samples without changing measurement windows."""
import copy
import math

import pytest

from dranalyser.workbench.incident_report_focus import attach_waveform_focus
from dranalyser.workbench.incident_report import build_incident_report
from tests.test_incident_reader_model import captures as captures, revision, saved_inputs


def fixture(*, count=1001, frequency=50, fault=(.4, .5)):
    times = [i/(count-1) for i in range(count)]
    values = [math.sin(2*math.pi*50*t) for t in times]
    prepared = dict(nominal_frequency_hz=frequency, axis={'elapsed_s': times},
                    channels=[dict(key='A1', values=values)])
    report = dict(region_support={'fault': {'time_range_s': list(fault)}} if fault else {},
        groups={'current': [dict(id='A1', units='A', trace=[[0, 0., 1.]])], 'voltage': []})
    return report, prepared


def test_native_focus_is_exact_source_local_and_does_not_change_original_traces_or_measurements():
    report, prepared = fixture()
    original = copy.deepcopy((report, prepared))
    attach_waveform_focus(report, prepared)
    focus = report['waveform_focus']
    assert focus['status'] == 'available' and focus['context_s'] == .04
    assert focus['time_range_s'] == pytest.approx([.36, .54])
    assert focus['native_indices'] == [360, 541] and focus['sample_count'] == 181
    assert focus['trace_policy'] == 'native samples'
    assert not focus['authorizes_location'] and not focus['changes_measurement_windows']
    channel = report['groups']['current'][0]
    assert channel['trace'] == original[0]['groups']['current'][0]['trace']
    assert channel['focus_trace'] == [[i, prepared['axis']['elapsed_s'][i], prepared['channels'][0]['values'][i]]
                                     for i in range(360, 541)]
    assert report['region_support'] == original[0]['region_support'] and prepared == original[1]


@pytest.mark.parametrize('frequency', [None, 0, 1, 100, '50', float('nan'), float('inf')])
def test_unknown_or_unsupported_frequency_never_defaults_to_50(frequency):
    report, prepared = fixture(frequency=frequency)
    attach_waveform_focus(report, prepared)
    assert report['waveform_focus']['status'] == 'unavailable'
    assert 'no frequency is assumed' in report['waveform_focus']['reason']
    assert 'focus_trace' not in report['groups']['current'][0]


def test_missing_fault_keeps_full_capture_and_no_event_is_inferred():
    report, prepared = fixture(fault=None)
    attach_waveform_focus(report, prepared)
    assert report['waveform_focus']['status'] == 'unavailable'
    assert 'bounded during-event' in report['waveform_focus']['reason']
    assert report['groups']['current'][0]['trace'] == [[0, 0., 1.]]


def test_context_clips_to_actual_capture_and_keeps_real_zero_count_samples():
    report, prepared = fixture(fault=(0., .02))
    report['groups']['current'][0]['units'] = 'counts'
    prepared['channels'][0]['values'][0] = 0.
    attach_waveform_focus(report, prepared)
    assert report['waveform_focus']['time_range_s'] == [0., .06]
    assert report['groups']['current'][0]['focus_trace'][0] == [0, 0., 0.]
    assert report['groups']['current'][0]['units'] == 'counts'


def test_null_observations_and_decode_gap_have_explicit_native_breaks():
    report, prepared = fixture()
    prepared['channels'][0]['values'][420] = None
    attach_waveform_focus(report, prepared, breaks=[450])
    trace = report['groups']['current'][0]['focus_trace']
    assert [420, .42, None] in trace
    index = trace.index([450, .45, None])
    assert trace[index+1] == [450, .45, prepared['channels'][0]['values'][450]]


def test_dense_focus_has_explicit_retention_budget_and_does_not_bridge_bucket_gaps():
    report, prepared = fixture(count=20001, fault=(.1, .9))
    prepared['channels'][0]['values'][7000] = None
    attach_waveform_focus(report, prepared, breaks=[8100, 12000])
    focus = report['waveform_focus']
    trace = report['groups']['current'][0]['focus_trace']
    assert focus['sample_count'] > 2048
    assert focus['trace_policy'] == 'retained sample envelope'
    assert len(trace) <= 2048
    assert any(point[2] is None for point in trace)
    assert all(value is None or value == prepared['channels'][0]['values'][index]
               for index, _, value in trace)
    for index, time, _ in trace:
        assert time == prepared['axis']['elapsed_s'][index]


def test_many_decode_breaks_are_bounded_and_cannot_become_a_dense_false_line():
    report, prepared = fixture(count=10001, fault=(.1, .9))
    attach_waveform_focus(report, prepared, breaks=range(1000, 9000))
    trace = report['groups']['current'][0]['focus_trace']
    assert len(trace) <= 2048 and any(value is None for _, _, value in trace)


def test_canonical_focus_uses_same_prepared_scaling_and_axis_breaks(captures):
    capture = captures['one.cfg']
    capture['channels'][3]['units'] = 'counts'
    capture['axis']['break_indices'] = [160]
    original = copy.deepcopy(capture)
    model = build_incident_report('.', revision(), records=['one.cfg'], event_inputs=saved_inputs(captures))
    source = model['sources'][0]
    channel = next(row for row in source['groups']['current'] if row['meaning'] == 'IA')
    assert channel['units'] == 'counts'
    assert [160, capture['axis']['elapsed_s'][160], None] in channel['focus_trace']
    assert 160 in source['gaps']['break_indices']
    assert all(value is None or value == capture['channels'][3]['values'][index]
               for index, _, value in channel['focus_trace'])
    assert capture == original
