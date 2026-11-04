"""Frozen report samples, scales and precise values remain honest on screen."""
import copy
import json
import re
from html import unescape

from dranalyser.report.incident_summary import render_incident_report
from tests.test_incident_summary import model, source


def chart_data(html):
    return [json.loads(value) for value in re.findall(
        r'<script type="application/json" class="waveform-data">(.*?)</script>', html)]


def test_rms_tooltip_preserves_full_stored_number_and_stated_measurement_basis():
    evidence = source(value=1234.5678901234567)
    evidence['phase_values'][0]['rms_basis'] = 'Known one-cycle RMS basis'
    evidence['phase_values'][0]['scaling_note'] = 'Known reviewed primary scaling'
    html = unescape(render_incident_report(model(evidence)))
    assert '<span class="value">1.235</span>' in html
    assert 'title="R (A) · fault: 1234.5678901234567 A primary. Known one-cycle RMS basis Known reviewed primary scaling"' in html
    assert 'aria-label="R (A) · fault: 1234.5678901234567' in html
    assert 'tabindex="0"' in html


def test_hover_data_stores_actual_raw_sample_value_and_not_rounded_display_number():
    evidence = model(source(value=1234.5678901234567))
    before = copy.deepcopy(evidence)
    html = render_incident_report(evidence)
    data = chart_data(html)
    assert len(data) == 2
    current = data[0]['channels'][0]
    assert current['units'] == 'kA' and current['original_units'] == 'A'
    assert current['factor'] == 1000
    assert current['trace'][1] == [1, .01, 1234.5678901234567]
    assert current['trace'][2] == [2, .02, None]
    assert 'Instantaneous samples; nearest retained observation, no interpolation.' in html
    assert evidence == before


def test_available_native_focus_uses_its_own_frozen_source_times_and_samples():
    evidence = source(value=1200)
    evidence['waveform_focus'] = dict(status='available', time_range_s=[.01, .03], trace_policy='native samples')
    for channels in evidence['groups'].values():
        for channel in channels:
            channel['focus_trace'] = [[1, .01, 42], [2, .02, 0], [3, .03, -17]]
    html = render_incident_report(model(evidence))
    data = chart_data(html)
    assert data[0]['range'] == [.01, .03]
    assert data[0]['trace_policy'] == 'native samples'
    assert data[0]['channels'][0]['trace'] == [[1, .01, 42], [2, .02, 0], [3, .03, -17]]
    assert 'Event detail · instantaneous values' in html
    assert 'data-waveform-mode-button="overview"' in html
    assert 'data-waveform-mode="overview" hidden' in html
    assert '.waveform-mode-panel[data-waveform-mode="focus"]{display:block!important}' in html
    assert '.waveform-mode-panel[data-waveform-mode="overview"]{display:none!important}' in html
    assert evidence['groups']['current'][0]['trace'][1][2] == 1200


def test_old_or_incomplete_focus_data_keeps_historical_overview_trace_available():
    evidence = source(value=1200)
    evidence['waveform_focus'] = dict(status='available', time_range_s=[.01, .03])
    data = chart_data(render_incident_report(model(evidence)))
    assert data[0]['range'] == [0, .04]
    assert data[0]['channels'][0]['trace'][1][2] == 1200
    assert 'Capture overview' in render_incident_report(model(evidence))


def test_zero_axis_and_shared_phase_scaling_keep_counts_and_units_separate():
    evidence = source(units='counts', value=7001)
    html = render_incident_report(model(evidence))
    data = chart_data(html)
    assert data[0]['channels'][0]['units'] == 'counts'
    assert data[0]['channels'][0]['factor'] == 1
    assert data[0]['channels'][0]['trace'][0][2] == 0
    assert html.count('class="grid zero-line"') == 2
    assert 'shared phase scale' in html
    assert '0 kA' not in html


def test_json_payload_cannot_close_its_script_or_execute_source_text():
    evidence = source(value=5)
    hostile = '</script><script>alert("source")</script>&'
    evidence['groups']['current'][0].update(meaning=None, label=hostile)
    html = render_incident_report(model(evidence))
    assert hostile not in html
    assert chart_data(html)[0]['channels'][0]['label'] == hostile
    assert '\\u003c/script\\u003e' in html
    assert '<script src=' not in html
    assert '<script>alert(' not in html


def test_fixed_print_pages_remain_and_interactive_controls_are_screen_only():
    html = render_incident_report(model(source(), source('other.cfg')))
    assert html.count('<section class="page"') == 4
    assert html.count('class="measurement-panels"') == 2
    assert html.count('class="waveform-view"') == 4
    assert '.waveform-readout{display:none!important}' in html
    assert 'Each recording has its own vertical scale' in html
    assert 'Effective values (RMS) · each phase' in html
