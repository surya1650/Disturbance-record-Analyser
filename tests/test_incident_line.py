"""Line geometry and CB observations retain source, end and eligibility evidence."""
import copy
import json
import math

import pytest

from dranalyser.workbench.incident_line import build_line_diagram
from dranalyser.workbench.incident_report import build_incident_report
from dranalyser.workbench.location_summary import bind_summary
from tests import test_incident_reader_model as reader_fixtures

analysed_demo = reader_fixtures.analysed_demo


def declared():
    facts = dict(id='LINE', name='Declared line', kv=220, length_km=100, sha256='line-hash',
        terminals=dict(S='Station S', R='Station R'), parameter_status='unverified',
        provenance='Frozen revision line.yaml.')
    row = dict(incident_id='incident', number=1, metadata={},
        files=[dict(name=end+'/'+name, sha256=end+'-'+name) for end in ('S', 'R')
               for name in ('event.cfg', 'event.dat')],
        bundle=dict(files=[dict(name=end+'/event.cfg', data_file=end+'/event.dat',
            terminal_end=end, role='primary') for end in ('S', 'R')]),
        result=dict(used=dict(S='S/event.cfg', R='R/event.cfg')))
    summary = dict(version=1, line=dict(sha256='line-hash'),
        source_records=row['result']['used'])
    row['result']['location_summary'] = bind_summary(summary, row, 'unverified')
    sources = [dict(record=end+'/event.cfg', source_sha256={name: end+'-'+name
        for name in ('event.cfg', 'event.dat')}, digital=dict(events=[])) for end in ('S', 'R')]
    location = dict(status='Existing conditional estimate', reference='S', method='E5',
        km_from_S=42, km_from_R=58, line_sha256='line-hash', reason='Existing eligible result.')
    return row, facts, sources, location


def test_known_42km_uses_full_line_and_named_physical_ends_without_new_location(analysed_demo):
    store, row = analysed_demo
    original = copy.deepcopy(row)
    report = build_incident_report(store.root, row)
    diagram = report['line_diagram']
    assert diagram['version'] == 1
    assert diagram['line']['length_km'] == 100
    assert diagram['line']['kv'] == 220
    assert diagram['terminals']['S']['label'] == 'Synthetic S'
    assert diagram['terminals']['R']['label'] == 'Synthetic R'
    assert diagram['terminals']['S']['record'] == 'S/event.cfg'
    assert diagram['terminals']['R']['record'] == 'R/event.cfg'
    assert diagram['fault']['method'] == 'E5'
    assert diagram['fault']['km_from_S'] == 41.98828243177587
    assert diagram['fault']['km_from_R'] == pytest.approx(58.01171756822413)
    assert diagram['fault']['position_fraction'] == pytest.approx(.4198828243177587)
    assert diagram['connections']['status'] == 'not supplied'
    assert row == original
    json.dumps(report, allow_nan=False)


def test_reversing_display_sources_does_not_reverse_buses_or_distance(analysed_demo):
    store, row = analysed_demo
    report = build_incident_report(store.root, row, records=['R/event.cfg', 'S/event.cfg'])
    diagram = report['line_diagram']
    assert report['sources'][0]['record'] == 'R/event.cfg'
    assert diagram['terminals']['S']['record'] == 'S/event.cfg'
    assert diagram['terminals']['R']['record'] == 'R/event.cfg'
    assert diagram['fault']['km_from_S'] == 41.98828243177587
    single = build_incident_report(store.root, row, records=['R/event.cfg'])['line_diagram']
    assert single['terminals']['S']['record'] is None
    assert single['terminals']['R']['record'] == 'R/event.cfg'
    assert single['line']['length_km'] == 100
    assert single['fault']['status'] == 'unavailable'


@pytest.mark.parametrize('km', [0, 100])
def test_terminal_fault_positions_keep_real_zero(km):
    row, facts, sources, location = declared()
    location.update(km_from_S=km, km_from_R=100-km)
    fault = build_line_diagram(row, facts, sources, location)['fault']
    assert fault['status'] == 'eligible'
    assert fault['position_fraction'] == km/100
    assert fault['km_from_S'] == km and fault['km_from_R'] == 100-km


def test_mixed_section_reactance_fraction_is_not_used_as_physical_fraction():
    row, facts, sources, location = declared()
    facts['sections'] = [dict(from_km=0, to_km=60, x1_ohm_per_km=.1),
                         dict(from_km=60, to_km=100, x1_ohm_per_km=.6)]
    location.update(m=.2, km_from_S=60, km_from_R=40)
    fault = build_line_diagram(row, facts, sources, location)['fault']
    assert fault['position_fraction'] == .6
    assert fault['km_from_S'] == 60


@pytest.mark.parametrize('field,value', [('length_km', None), ('length_km', 0),
    ('length_km', math.inf), ('length_km', math.nan), ('sha256', 'changed-line')])
def test_missing_or_inconsistent_line_evidence_has_no_marker(field, value):
    row, facts, sources, location = declared()
    facts[field] = value
    diagram = build_line_diagram(row, facts, sources, location)
    assert diagram['fault']['position_fraction'] is None
    assert diagram['fault']['km_from_S'] is None
    assert diagram['fault']['reason']
    assert diagram['terminals']['S']['breaker']['state'] == 'unknown'
    json.dumps(diagram, allow_nan=False)


@pytest.mark.parametrize('field,value', [('km_from_S', math.nan), ('km_from_R', math.inf),
    ('km_from_S', -1), ('km_from_S', 101), ('km_from_R', 57), ('method', None),
    ('method', ' '), ('status', 'unavailable'), ('reference', 'R')])
def test_refused_invalid_distance_never_becomes_a_visual_fault(field, value):
    row, facts, sources, location = declared()
    location[field] = value
    fault = build_line_diagram(row, facts, sources, location)['fault']
    assert fault['status'] == 'unavailable'
    assert fault['position_fraction'] is None
    assert fault['method'] is None


def test_trip_commands_and_pole_observations_never_establish_breaker_position():
    row, facts, sources, location = declared()
    sources[0]['digital']['events'] = [dict(meaning='TRIP', plain_label='Trip command', kind='asserted',
        source_s=.14, source_bracket_s=[.139, .14], assertion_source='assumed high state',
        interpretation_available=True), dict(meaning='CB_OPEN_A', label='R pole open feedback',
        kind='state difference across gap', source_s=.2, source_bracket_s=[.15, .2],
        assertion_source='source-analysis choice', interpretation_available=False)]
    original = copy.deepcopy((row, facts, sources, location))
    breaker = build_line_diagram(row, facts, sources, location)['terminals']['S']['breaker']
    assert breaker['state'] == 'unknown'
    trip = breaker['trip_observations'][0]
    assert trip['source_s'] == .14 and not trip['polarity_reviewed']
    feedback = breaker['feedback_observations'][0]
    assert feedback['polarity_reviewed']
    assert feedback['source_bracket_s'] == [.15, .2]
    assert not feedback['transition_time_known']
    assert (row, facts, sources, location) == original


def test_stale_or_other_source_is_not_attached_to_a_physical_breaker():
    row, facts, sources, location = declared()
    row['result']['location_summary']['binding'] = {}
    diagram = build_line_diagram(row, facts, sources, location)
    assert all(end['record'] is None for end in diagram['terminals'].values())
    assert diagram['fault']['position_fraction'] is None
    row, facts, sources, location = declared()
    sources[0]['source_sha256']['event.dat'] = 'another-source'
    diagram = build_line_diagram(row, facts, sources, location)
    assert diagram['terminals']['S']['record'] is None
    assert diagram['fault']['position_fraction'] is None
    row, facts, sources, location = declared()
    row['bundle']['files'][0]['terminal_end'] = 'R'
    assert build_line_diagram(row, facts, sources, location)['terminals']['S']['record'] is None


def test_a_different_display_cohort_does_not_reuse_the_stored_marker():
    row, facts, sources, location = declared()
    diagram = build_line_diagram(row, facts, sources[1:], location)
    assert diagram['terminals']['R']['record'] == 'R/event.cfg'
    assert diagram['fault']['position_fraction'] is None


def test_missing_names_and_topology_stay_explicit_without_fabricated_connections():
    row, facts, sources, location = declared()
    facts['terminals'] = dict(S='Not available', R='')
    diagram = build_line_diagram(row, facts, sources, location)
    assert diagram['terminals']['S']['label'] == 'End S (name unavailable)'
    assert diagram['terminals']['R']['label'] == 'End R (name unavailable)'
    assert diagram['connections']['status'] == 'not supplied'
    assert 'other connected lines are not supplied' in diagram['connections']['note']
    assert all(terminal['breaker']['state'] == 'unknown' for terminal in diagram['terminals'].values())


def test_no_frozen_line_gives_generic_connections_and_no_invented_length_or_voltage():
    row, _, sources, location = declared()
    diagram = build_line_diagram(row, {}, sources, location)
    assert diagram['status'] == 'generic schematic'
    assert diagram['line']['length_km'] is None
    assert diagram['line']['kv'] is None
    assert diagram['line']['name'] is None
    assert diagram['fault']['position_fraction'] is None
    assert diagram['terminals']['S']['record'] is None
    assert diagram['terminals']['R']['record'] is None


def test_declared_provisional_length_can_show_without_releasing_a_fault_marker(analysed_demo):
    store, row = analysed_demo
    row = copy.deepcopy(row)
    row['result']['parameter_status'] = 'provisional'
    diagram = build_incident_report(store.root, row)['line_diagram']
    assert diagram['line']['length_km'] == 100
    assert diagram['line']['parameter_status'] == 'provisional'
    assert diagram['fault']['status'] == 'unavailable'
    assert diagram['fault']['position_fraction'] is None
