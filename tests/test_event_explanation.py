"""Concise conclusions preserve sample/source provenance and abstentions."""
import json

from dranalyser.workbench import event_study as study
from tests import test_event_study as fixtures

inputs = fixtures.inputs
model = fixtures.model


def test_observation_summary_has_changes_without_invented_fault_or_operation(model):
    _, row = model
    report = study.build_event_report('.', row, inputs())
    summary = report['explanation']
    observations = summary['observations']
    assert any('VA fell (-50%) [V]' in entry['text'] for entry in observations)
    assert any('IA rose (+400%) [A]' in entry['text'] for entry in observations)
    analog = next(entry for entry in observations if entry['kind'] == 'analog')
    assert analog['source_sha256'] == report['ends']['S']['source_sha256']
    assert analog['region_support']['fault'] == dict(indices=[100, 220], time_range_s=[.1, .219])
    assert not summary['interpretation']
    assert any('probable fault type is not established' in entry for entry in summary['uncertainty'])
    assert any('no interpreted pole/open' in entry for entry in summary['uncertainty'])
    assert summary['protection_verdict'].startswith('Not assessed')
    assert not summary['authorizes_location']
    digital = next(entry for entry in observations if entry['kind'] == 'digital')
    assert digital['events'][0]['source_bracket_s'] == [.129, .130]
    json.dumps(report, allow_nan=False)


def test_missing_short_or_ongoing_baseline_does_not_invent_change(model):
    _, row = model
    chosen = inputs()
    chosen['ends']['S'].update(pre=[0, 15], fault=None)
    summary = study.build_event_report('.', row, chosen)['explanation']
    assert not [entry for entry in summary['observations'] if entry['kind'] == 'analog']
    assert any('no healthy baseline is invented' in entry for entry in summary['uncertainty'])


def test_structured_matching_location_names_method_and_classification(model, monkeypatch):
    _, row = model
    row['result'] = dict(used={'S': 'S/event.cfg'}, location_text='legacy text', location_summary={'version': 1})
    facts = dict(length_km=100, terminals={'S': 'Alpha', 'R': 'Beta'}, parameter_status='declared',
                 provenance='frozen line', location=dict(text='42 km from S by E5', method='E5',
                 fault_type='AG', km_from_S=42, overlay_eligible=True, summary={'version': 1, 'status': 'accepted'}))
    monkeypatch.setattr(study, 'line_facts', lambda root, revision: facts)
    report = study.build_event_report('.', row, inputs())
    assert report['distance']['method'] == 'E5'
    assert report['explanation']['interpretation'][0]['fault_type'] == 'AG'
    assert '42 km from S by E5' in report['explanation']['interpretation'][1]['text']
    assert report['line']['length_km'] == 100
    assert not report['navigation']['available']
    mismatched = study.build_event_report('.', row, inputs(True))
    assert 'summary' not in mismatched['distance']
    assert not mismatched['explanation']['interpretation']
    facts['location']['overlay_eligible'] = False
    refused = study.build_event_report('.', row, inputs())
    assert not refused['explanation']['interpretation']
    assert refused['distance']['km_from_S'] is None


def test_structured_refusal_cannot_fall_back_to_legacy_method(model, monkeypatch):
    _, row = model
    row['result'] = dict(used={'S': 'S/event.cfg'}, location_summary={'status': 'refused'}, location_text='42 km from S by E5')
    monkeypatch.setattr(study, 'line_facts', lambda root, revision: dict(provenance='rejected binding',
        location=dict(text='Structured result binding is stale.', km_from_S=42, overlay_eligible=True), length_km=100))
    report = study.build_event_report('.', row, inputs())
    assert report['distance']['method'] is None
    assert report['distance']['km_from_S'] is None


def test_visual_navigation_is_limited_to_selected_analysed_sources(model):
    _, row = model
    row['result'] = dict(navigator_path='frozen/navigator.json', relay_evidence=[
        dict(file='S/event.cfg', status='analysed'), dict(file='R/event.cfg', status='analysed'),
        dict(file='other.cfg', status='analysed')])
    report = study.build_event_report('.', row, inputs())
    assert report['navigation']['available']
    assert report['navigation']['records'] == ['S/event.cfg']
    assert report['line']['length_km'] is None
