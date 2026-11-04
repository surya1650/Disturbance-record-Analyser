"""A fault diagram must keep distances, unknowns and indication meaning explicit."""
import copy
import re
from html import unescape

import pytest

from dranalyser.report.incident_line import line_diagram_view
from dranalyser.report.incident_summary import render_incident_report


def diagram(distance=42., *, length=100., method='E5'):
    return dict(version=1, status='declared line schematic',
        line=dict(id='Synthetic circuit 1', name='North–South', length_km=length, kv=220),
        terminals={end: dict(label=name, breaker=dict(state='unknown', trip_observations=[]))
                   for end, name in (('S', 'North station'), ('R', 'South station'))},
        fault=dict(status='eligible', method=method, km_from_S=distance,
                   km_from_R=length-distance if length is not None else None,
                   position_fraction=distance/length if length else None),
        connections=dict(note='Other connected circuits are not supplied.'))


def test_named_circuit_and_distances_use_physical_km_without_changing_evidence():
    evidence = diagram()
    evidence['fault']['m'] = .9  # Reactance fraction must not move a 42 km marker.
    original = copy.deepcopy(evidence)
    view = line_diagram_view(evidence)
    svg = str(view['svg'])
    assert view['has_fault'] and view['method'] == 'E5'
    assert 'Full line length: 100 km' in svg
    assert '42 km from S' in svg and '58 km from R' in svg
    assert 'data-position-fraction="0.42"' in svg
    marker = re.search(r'class="fault-marker".*?<path d="M ([0-9.]+) 69 L ([0-9.]+) 87', svg)
    assert marker
    marker_x = sum(float(value) for value in marker.groups())/2
    assert marker_x == pytest.approx(136+.42*(544-136))
    assert view['terminals']['S']['label'] == 'North station'
    assert view['terminals']['R']['label'] == 'South station'
    assert evidence == original


@pytest.mark.parametrize('distance,fraction', [(0., '0'), (100., '1')])
def test_end_point_distances_preserve_real_zero(distance, fraction):
    view = line_diagram_view(diagram(distance))
    svg = str(view['svg'])
    assert view['has_fault']
    assert 'data-position-fraction="'+fraction+'"' in svg
    assert '0 km from '+('S' if distance == 0 else 'R') in svg


@pytest.mark.parametrize('change', [dict(status='unavailable'), dict(method=None),
    dict(km_from_S=101), dict(km_from_R=59), dict(position_fraction=.9),
    dict(position_fraction=float('nan'))])
def test_no_arbitrary_marker_for_refused_or_inconsistent_distance(change):
    evidence = diagram()
    evidence['fault'].update(change)
    view = line_diagram_view(evidence)
    assert not view['has_fault']
    assert 'fault-marker' not in str(view['svg'])
    assert 'Fault position unavailable' in str(view['svg'])
    assert 'Full line length: 100 km' in str(view['svg'])


def test_missing_line_length_keeps_neutral_terminal_symbols_and_unknown_position():
    evidence = diagram(length=None)
    evidence['status'] = 'generic schematic'
    view = line_diagram_view(evidence)
    svg = str(view['svg'])
    assert not view['has_fault']
    assert 'Full line length: unavailable' in svg
    assert svg.count('class="diagram-cb"') == 2
    assert svg.count('position unknown') == 2
    assert 'stroke-dasharray="6 4"' in svg
    assert 'open' not in svg.lower() and 'closed' not in svg.lower()
    assert view['connections_note'] == 'Other connected circuits are not supplied.'


def test_trip_observations_retain_source_clock_and_gap_uncertainty():
    evidence = diagram()
    evidence['terminals']['S']['breaker']['trip_observations'] = [dict(
        kind='asserted', source_s=.14, polarity_reviewed=False)]
    evidence['terminals']['R']['breaker']['trip_observations'] = [dict(
        kind='state difference across gap', source_s=.5, source_bracket_s=[.2, .5], polarity_reviewed=True)]
    view = line_diagram_view(evidence)
    assert '0.14 s local' in view['observations'][0]
    assert 'polarity unverified' in view['observations'][0]
    assert '0.2–0.5 s local; transition time unknown' in view['observations'][1]
    assert 'open/closed state unknown' in view['state_note']


def test_signal_clearance_is_not_presented_as_a_trip_or_confirmed_breaker_position():
    evidence = diagram()
    evidence['terminals']['S']['breaker']['trip_observations'] = [dict(
        kind='cleared', source_s=.14, polarity_reviewed=False)]
    evidence['terminals']['R']['breaker']['feedback_observations'] = [dict(
        signal='R-phase open indication', kind='cleared', source_s=.21,
        polarity_reviewed=True, interpretation_available=True)]
    view = line_diagram_view(evidence)
    assert 'Trip signal low state' in view['observations'][0]
    assert 'polarity unverified' in view['observations'][0]
    assert 'R-phase open indication cleared' in view['observations'][1]
    assert 'open/closed state unknown' in view['state_note']


def test_provisional_declared_length_stays_visible_when_location_is_refused():
    evidence = diagram()
    evidence['line'].update(sha256='frozen-model-sha', parameter_status='provisional')
    evidence['fault'].update(status='unavailable', method=None)
    view = line_diagram_view(evidence)
    assert 'Declared line model (provisional)' in view['provenance_note']
    assert 'Full line length: 100 km' in str(view['svg'])
    assert not view['has_fault']


def test_report_escapes_circuit_and_terminal_labels_and_keeps_four_sheets():
    evidence = diagram()
    hostile = '<img src=x onerror=alert(1)>'
    evidence['line']['name'] = hostile
    evidence['terminals']['S']['label'] = hostile
    model = dict(incident_id='synthetic', revision=1, version=1, line_diagram=evidence,
        location=dict(km_from_S=42, method='E5', reference_label=hostile))
    html = render_incident_report(model)
    assert html.count('<section class="page"') == 4
    assert 'class="incident-line-diagram"' in html
    assert '<img ' not in html
    assert '&lt;img src=x onerror=alert(1)&gt;' in html
    assert 'Calculated by E5' in unescape(re.sub('<[^>]+>', ' ', html))
    assert 'open/closed state unknown' in html


def test_older_report_models_keep_their_existing_layout():
    assert line_diagram_view(None) is None
    assert line_diagram_view({'version': 99}) is None
    html = render_incident_report(dict(incident_id='old', revision=1, version=1))
    assert '<figure class="incident-line-diagram"' not in html
    assert html.count('<section class="page"') == 4
