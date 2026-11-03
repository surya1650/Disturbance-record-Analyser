"""Reader HTML preserves evidence boundaries and offline print structure."""
import copy
import re
from html import unescape

from dranalyser.report.incident_summary import render_incident_report


def source(record='first.cfg', *, units='A primary', value=0):
    rows, traces = [], []
    for meaning in ('IA', 'IB', 'IC', 'VA', 'VB', 'VC'):
        unit = units if meaning.startswith('I') else 'V primary'
        rows.append(dict(meaning=meaning, label=meaning, units=unit, pre_rms=0,
            fault_rms=value, post_rms=None, missing_reasons=dict(post='Capture ends before a supported after-event interval.')))
        traces.append(dict(meaning=meaning, units=unit,
            trace=[[0, 0, 0], [1, .01, value], [2, .02, None], [3, .03, value], [4, .04, 0]]))
    return dict(record=record, display_label='Recording '+record, time_range_s=[0, .04], phase_values=rows,
        groups=dict(current=traces[:3], voltage=traces[3:]), region_support={},
        digital=dict(events=[], total_events=0), rms_basis='Median of complete one-cycle RMS observations.')


def model(*sources):
    return dict(version=1, kind='incident-reader-report', incident_id='synthetic-1', revision=4,
        sources=list(sources), summary=dict(headline='Recorded disturbance', text='Known observations only.'),
        location=dict(km_from_S=None, reason='No reviewed physical end assignment is available.'))


def visible_text(html):
    return unescape(re.sub('<[^>]+>', ' ', html))


def test_four_offline_sheets_preserve_zeros_counts_and_the_input_model():
    evidence = model(source(units='counts', value=734))
    original = copy.deepcopy(evidence)
    html = render_incident_report(evidence)
    text = visible_text(html)
    assert html.count('<section class="page"') == 4
    assert 'data-report-model-version="1"' in html
    assert '@page{size:A4;margin:0}' in html
    assert 'window.print()' in html
    assert '<script' not in html and 'src=' not in html and 'href=' not in html
    assert '<span class="value">0</span>' in html
    assert '<span class="value">734</span> <span class="unit">counts</span>' in html
    assert 'Capture ends before a supported after-event interval.' in text
    assert 'No reviewed physical end assignment is available.' in text
    assert 'R (A)' in text and 'Y (B)' in text and 'B (C)' in text
    assert '<span class="unit">kA</span>' not in html
    assert evidence == original


def test_html_and_svg_source_text_are_escaped():
    hostile = '<img src=x onerror=alert(1)>'
    evidence = model(source(hostile, units=hostile))
    evidence['title'] = hostile
    evidence['summary']['text'] = hostile
    evidence['generation'] = dict(created_at=hostile, timezone=hostile)
    evidence['location']['reason'] = hostile
    html = render_incident_report(evidence)
    assert hostile not in html
    assert '&lt;img src=x onerror=alert(1)&gt;' in html
    assert '<img' not in html


def test_waveform_paths_do_not_bridge_null_observations():
    html = render_incident_report(model(source(value=12)))
    # Six tracks, each with one segment on each side of the null observation.
    assert html.count('<polyline ') == 12
    assert html.count('<svg ') == 2
    assert 'Source-local time (s)'  in html
    assert 'Gaps remain unknown.' in html


def test_missing_first_source_cannot_hide_second_source_values():
    unavailable = dict(record='broken.cfg', status='unavailable', reason='Known strictly increasing source times are required.',
        phase_values=[], groups={}, digital={})
    html = render_incident_report(model(unavailable, source('second.cfg', value=1937)))
    assert '<span class="value">1.937</span> <span class="unit">kA</span>' in html
    assert 'second.cfg' in html
    assert 'Known strictly increasing source times are required.' in html
    assert 'No mapped current waveform is available' in html


def test_sources_events_and_attachment_omissions_are_explicit():
    first = source('one.cfg')
    first['digital'] = dict(total_events=7, events=[dict(source_s=i, label='Signal '+str(i),
        kind='asserted', interpretation_available=False, meaning='') for i in range(7)])
    evidence = model(first, source('two.cfg'), source('three.cfg'))
    evidence['attachments'] = [dict(record='one.cfg', status='included', reason='Selected'),
        dict(record='three.cfg', status='attached; not plotted', reason='A third recording remains attached.')]
    html = render_incident_report(evidence)
    text = visible_text(html)
    assert '1 further recording(s) are omitted from these plots.' in text
    assert '1 additional attachment' in text
    assert '3 additional change(s) omitted here' in text
    assert 'Signal 3' in text and 'Signal 4' not in text
    assert 'State change' in text
    assert 'Trip and close indications are recorded signals or commands.' in text


def test_native_fault_rms_is_labelled_separately_and_has_its_own_window():
    first = source(value=123)
    first['operational_measurements'] = dict(status='stored', window=dict(start_s=.02, end_s=.039),
        channels=[dict(channel='IA', rms=98, unit='A primary')])
    html = render_incident_report(model(first))
    assert 'Stored fault-window sample RMS:' in html
    assert 'R (A): 98 A' in html
    assert '0.02 to 0.039 s' in html
    assert 'Separate sample-weighted basis, not the table’s one-cycle median.' in html
    assert '<span class="value">123</span>' in html


def test_location_requires_a_named_method_and_preserves_zero_distance():
    evidence = model(source())
    evidence['location'] = dict(km_from_S=0, method='E5', reference_label='Named sending station', reason='Eligible stored estimate.')
    html = render_incident_report(evidence)
    assert '<div class="fact-value">0 km</div>' in html
    assert '<strong>E5</strong> · From Named sending station' in html
    evidence['location'].pop('method')
    assert '<div class="fact-value">Not available</div>' in render_incident_report(evidence)


def test_metric_prefixes_only_format_declared_physical_units_and_preserve_source_values():
    first = source(value=126999)
    original = copy.deepcopy(first)
    html = render_incident_report(model(first, source('raw.cfg', units='raw counts', value=1937)))
    assert '<span class="value">126.999</span> <span class="unit">kA</span>' in html
    assert '<span class="value">126.999</span> <span class="unit">kV</span>' in html
    assert '<span class="value">1,937</span> <span class="unit">raw counts</span>' in html
    assert 'instrument scaling unverified' in html
    assert first == original


def test_signal_polarity_assumption_and_gap_interval_survive_presentation():
    first = source()
    first['digital'] = dict(events=[
        dict(source_s=.02, meaning='TRIP', kind='asserted', interpretation_available=True,
             assertion_source='assumed high state'),
        dict(source_s=.03, source_bracket_s=[.02, .03], meaning='CARRIER_RECV',
             kind='state difference across gap', interpretation_available=False)])
    html = render_incident_report(model(first))
    assert 'Trip command indication' in html
    assert 'High state*' in html
    assert 'High state is assumed active; signal polarity is unverified.' in html
    assert 'Protection message received' in html
    assert '0.02–0.03 s' in html
    assert 'Across gap; time unknown' in html
