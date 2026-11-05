"""Readable frozen signal/clock summaries retain uncertainty and raw zero states."""
import copy
import json
import re
from html import unescape

from dranalyser.report.incident_summary import _signal_rows, render_incident_report
from tests.test_incident_summary import model, source


def recording():
    value = source(value=1234)
    value['record_clock'] = dict(start_display='05 Nov 2026 08:00:00.123456',
        trigger_display='05 Nov 2026 08:00:00.223456', timezone_label='Not declared',
        cursor_time_status='unavailable', cursor_time_reason='Cursor uses elapsed source time.')
    def channel(label, asserted, raw, active, bounds):
        return dict(id=label, label=label, asserted_state=asserted,
            segments=[dict(from_s=0., to_s=.01, from_index=0, to_index=1, state=raw)],
            window_summary=dict(time_range_s=[0., .04], raw_state_at_start=raw,
                asserted_at_start=raw == asserted if asserted is not None else None,
                active_during_window=active, duration_bounds_s=bounds,
                high_duration_bounds_s=[0., .005], observed_high_span_s=0.,
                reason='Known sampled-state evidence, not physical operation.'))
    value['digital']['inspection'] = dict(total_channels=12, omitted_channels=8, channels=[
        channel('Active-low trip', 0, 0, True, [.01, .015]),
        channel('Unreviewed high', None, 1, None, None),
        channel('Recorded zero', 1, 0, False, [0., 0.]),
        dict(id='Unknown', label='Unknown', asserted_state=1,
            window_summary=dict(status='unavailable', reason='No selected during-event interval.'))])
    return value


def data_blocks(html):
    return [json.loads(value) for value in re.findall(
        r'<script type="application/json" class="waveform-data">(.*?)</script>', html)]


def test_print_summary_keeps_active_low_raw_zero_uncertain_bounds_and_unknowns():
    recording_source = recording()
    rows = _signal_rows(recording_source['digital'])
    assert rows[0]['state'] == 'Asserted · Low (0)'
    assert rows[0]['activity'] == 'Yes' and rows[0]['span'] == '10 ms–15 ms'
    assert rows[1]['state'] == 'High (1)' and rows[1]['activity'] == 'Polarity unreviewed'
    assert rows[1]['span'] == 'High 0 ms–5 ms'
    assert rows[2]['state'] == 'Cleared · Low (0)' and rows[2]['activity'] == 'No'
    assert rows[2]['span'] == '0 ms'
    assert rows[3]['state'] == rows[3]['span'] == 'Unavailable'
    assert rows[3]['activity'] == 'Unavailable'


def test_record_dates_remain_visible_with_line_diagram_and_digital_window_table():
    evidence = model(recording())
    evidence['line_diagram'] = dict(version=1, line=dict(length_km=45), terminals={}, fault={})
    before = copy.deepcopy(evidence)
    html = render_incident_report(evidence)
    text = unescape(re.sub('<[^>]+>', ' ', html.split('<script>')[0]))
    assert html.count('<section class="page"') == 4
    assert 'signal-table signal-window-table' in html
    assert 'Recorded trigger: 05 Nov 2026 08:00:00.223456' in text
    assert 'Recorded start: 05 Nov 2026 08:00:00.123456' in text
    assert 'Recorder local · time zone Not declared' in text
    assert 'During-event window: 0–0.04 local s' in text
    assert '4 of 12 digital channels shown.' in text
    assert 'Asserted · Low (0)' in text and 'High 0 ms–5 ms' in text
    assert 'not physical operating time' in text
    assert evidence == before


def test_cursor_payload_contains_bounded_states_and_raw_record_clock_without_projection():
    evidence = recording()
    html = render_incident_report(model(evidence))
    for block in data_blocks(html):
        assert block['digital_inspection'] == evidence['digital']['inspection']
        assert block['record_clock'] == evidence['record_clock']
        assert block['record_clock']['cursor_time_status'] == 'unavailable'
    assert 'class="waveform-readout" role="status"' in html
    assert '.waveform-readout{display:none!important}' in html


def test_missing_polarity_or_window_never_becomes_an_assertion_or_zero_duration():
    rows = _signal_rows(dict(inspection=dict(channels=[dict(label='No window', asserted_state=None)])))
    assert rows[0]['state'] == rows[0]['span'] == 'Unavailable'
    assert rows[0]['activity'] == 'Polarity unreviewed'
    assert _signal_rows({}) == []
    rows = _signal_rows(dict(inspection=dict(channels=[dict(asserted_state=True,
        window_summary=dict(raw_state_at_start=1, asserted_at_start=True, active_during_window=True))])))
    assert rows[0]['state'] == 'High (1)' and rows[0]['activity'] == 'Polarity unreviewed'
    rows = _signal_rows(dict(inspection=dict(channels=[dict(asserted_state=1,
        window_summary=dict(raw_state_at_start=None, asserted_at_start=True))])))
    assert rows[0]['state'] == 'Unavailable'


def test_partial_observed_spans_are_marked_without_inventing_clearing_time():
    evidence = recording()
    summary = evidence['digital']['inspection']['channels'][0]['window_summary']
    summary.update(censored_start=True, gap_count=1)
    rows = _signal_rows(evidence['digital'])
    assert rows[0]['span'] == '10 ms–15 ms *' and rows[0]['partial']
    html = render_incident_report(model(evidence))
    assert '* Boundary or missing observations limit the span' in html


def test_state_clock_and_json_text_are_escaped_and_old_clock_fields_still_display():
    hostile = '</script><img src=x onerror=bad()>'
    evidence = recording()
    evidence['record_clock']['start_display'] = hostile
    evidence['digital']['inspection']['channels'][0]['label'] = hostile
    html = render_incident_report(model(evidence))
    assert hostile not in html and '<img src=x' not in html
    assert data_blocks(html)[0]['record_clock']['start_display'] == hostile
    assert data_blocks(html)[0]['digital_inspection']['channels'][0]['label'] == hostile
    old = source()
    old['recorded_times'] = dict(start='04/11/2026,23:45:00.000000', trigger='04/11/2026,23:45:00.100000')
    old_html = render_incident_report(model(old))
    assert '04/11/2026,23:45:00.100000' in old_html
    assert data_blocks(old_html)[0]['record_clock']['start_display'] == old['recorded_times']['start']
    assert data_blocks(old_html)[0]['record_clock']['timezone_label'] == 'Not declared'


def test_inspection_table_does_not_repeat_assumed_high_active_or_hidden_timeline_claims():
    evidence = recording()
    evidence['digital'].update(total_events=7, insights=[
        'Unreviewed high already active at capture start under stated polarity.'], events=[
        dict(source_s=i/100, meaning='TRIP', kind='asserted', interpretation_available=True,
             assertion_source='assumed high state') for i in range(7)])
    text = unescape(re.sub('<[^>]+>', ' ', render_incident_report(model(evidence)).split('<script>')[0]))
    assert '7 capture change(s); timeline in saved evidence.' in text
    assert '3 additional change(s) omitted' not in text
    assert 'already active at capture start' not in text
    assert 'assumed active' not in text
    evidence['digital']['inspection']['channels'] = [dict(label='No selected window', asserted_state=None)]
    assert 'No bounded during-event sample interval is available.' in render_incident_report(model(evidence))
