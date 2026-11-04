"""Native classifications may be shown when physical distance has been refused."""
import copy

import pytest

from dranalyser.workbench.incident_report import build_incident_report
from dranalyser.workbench import event_study
from tests.test_incident_reader_model import analysed_demo as analysed_demo


def refused(row):
    row = copy.deepcopy(row)
    summary = row['result']['location_summary']
    summary.update(accepted=False, status='refused', method=None, km_from_S=None, km_from_R=None)
    row['result']['location_text'] = 'refused - synthetic quality gate'
    return row


def test_bound_native_classification_survives_location_refusal_without_new_distance(analysed_demo):
    store, row = analysed_demo
    row = refused(row)
    original = copy.deepcopy(row)
    model = build_incident_report(store.root, row)
    classification = model['summary']['classification']
    assert model['location']['km_from_S'] is None
    assert classification['code'] == 'AG' and classification['label'] == 'R phase to earth'
    assert classification['status'] == 'stored source classification'
    assert not classification['authorizes_location']
    assert {source['record'] for source in classification['sources']} == set(row['result']['used'].values())
    assert row == original


def test_native_disagreement_remains_explicit_and_no_loop_is_selected(analysed_demo):
    store, row = analysed_demo
    row = refused(row)
    row['result']['relay_evidence'][0]['fault_type'] = 'BC'
    model = build_incident_report(store.root, row)
    classification = model['summary']['classification']
    assert classification['status'] == 'disagreement'
    assert classification['label'] == 'Recordings disagree' and classification['code'] is None
    assert {source['code'] for source in classification['sources']} == {'AG', 'BC'}
    assert model['location']['km_from_S'] is None


def test_one_unknown_native_classification_does_not_promote_the_other(analysed_demo):
    store, row = analysed_demo
    row = refused(row)
    row['result']['relay_evidence'][0]['fault_type'] = 'NONE'
    classification = build_incident_report(store.root, row)['summary']['classification']
    assert classification['status'] == 'partial' and classification['code'] is None
    assert any(source['code'] is None for source in classification['sources'])


@pytest.mark.parametrize('change', ['binding', 'record_hash', 'missing_record_hash', 'role', 'status', 'cohort'])
def test_stale_unanalysed_or_wrong_cohort_classification_is_not_exposed(analysed_demo, change):
    store, row = analysed_demo
    row = refused(row)
    if change == 'binding':
        row['result']['location_summary']['binding'] = {}
    elif change in ('record_hash', 'missing_record_hash'):
        row['result']['relay_evidence'][0]['record_hash'] = 'stale' if change == 'record_hash' else ''
    elif change == 'role':
        row['bundle']['files'][0]['role'] = 'corroborating'
    elif change == 'status':
        row['result']['relay_evidence'][0]['status'] = 'unavailable'
    else:
        row['result']['used'] = {'S': 'S/event.cfg'}
    classification = build_incident_report(store.root, row)['summary']['classification']
    assert classification['status'] == 'unavailable' and classification.get('code') is None


def test_accepted_result_unknown_classification_is_preserved(analysed_demo):
    store, row = analysed_demo
    row['result']['location_summary']['fault_type'] = 'NONE'
    model = build_incident_report(store.root, row)
    assert model['location']['km_from_S'] is not None
    assert model['summary']['classification']['label'] == 'Not established'


def test_display_phase_mapping_change_cannot_reuse_native_classification(analysed_demo):
    store, row = analysed_demo
    row = refused(row)
    inputs = dict(version=1, inputs={'ends': {}}, bindings={})
    for end in ('S', 'R'):
        capture, _ = event_study._source(store.root, row, end+'/event.cfg')
        inputs['inputs']['ends'][end] = dict(record=end+'/event.cfg', timing_mode='auto', mappings={'A1': 'VB'})
        inputs['bindings'][end] = capture['source_sha256']
    classification = build_incident_report(store.root, row, event_inputs=inputs)['summary']['classification']
    assert classification['status'] == 'unavailable' and classification.get('code') is None
