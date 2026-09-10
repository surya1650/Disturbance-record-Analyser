"""Application revisions retain per-relay profiles, settings and advisory audit scope."""
import json

import pytest

from dranalyser.application.intake import metadata_value
from dranalyser.application.worker import Worker
from tests import test_application as fixtures
from tests.test_evidence_application import pair_payload
from tests.test_settings import RIO_FIXTURE

environment = fixtures.environment


def test_per_relay_settings_and_profiles_survive_late_export_and_new_revision(environment):
    client, app, source, registry = environment
    assignments = {f'S/{s}/event.cfg': {'end': 'S', 'role': 'primary' if s == 'Main-1' else 'corroborating',
                                     'protection_system': s, 'recording_profile': 'wg3-220plus-distance'}
                   for s in ('Main-1', 'Main-2')}
    def export(system, delay):
        text = RIO_FIXTURE+f'BEGIN ZONE\nNAME Z2\nTIME1 {delay}\nEND ZONE\n'
        return ('files', (f'S/{system}/event.rio', text.encode()))
    files = pair_payload(source, 'S', 'Main-1') + pair_payload(source, 'S', 'Main-2', change=True)
    files.append(export('Main-1', .3))
    response = client.post('/api/intake', files=files, data={'metadata': json.dumps({
        'assignments': assignments, 'auto_analyse': True})})
    identity = response.json()['incident_id']
    worker = Worker(app.state.store, registry)
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    assert row['state'] == 'completed', row.get('error')
    audits = {a['protection_system']: a for a in row['result']['standards_audits']}
    assert len(audits['Main-1']['digital_profile']['points']) == 42
    assert audits['Main-2']['settings_source']['status'] == 'not supplied'
    assert all(c['status'] == 'not_evaluable' for c in audits['Main-2']['settings_checks'])
    assert next(c for c in audits['Main-1']['settings_checks'] if c['id'] == 'SET-Z2-TIME')['status'] == 'gap'
    first = client.get(f'/api/incidents/{identity}/report?revision=1').content
    assert b'Recording and philosophy checklists' in first
    response = client.post('/api/intake', files=[export('Main-2', .35)], data={
        'incident_id': identity, 'expected_revision': 1,
        'metadata': json.dumps({'assignments': assignments, 'auto_analyse': True})})
    assert response.status_code == 202, response.text
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    assert row['state'] == 'completed', row.get('error')
    audits = {a['protection_system']: a for a in row['result']['standards_audits']}
    assert audits['Main-2']['settings_source']['file'] == 'S/Main-2/event.rio'
    assert next(c for c in audits['Main-2']['settings_checks'] if c['id'] == 'SET-Z2-TIME')['status'] == 'pass'
    assert next(c for c in audits['Main-2']['settings_checks'] if c['id'] == 'SET-VALIDITY')['status'] == 'not_evaluable'
    assert client.get(f'/api/incidents/{identity}/report?revision=1').content == first


def test_recording_profile_is_explicit_validated_metadata():
    assignment = {'end': 'S', 'role': 'primary', 'protection_system': 'Main-1'}
    assert 'recording_profile' not in metadata_value({'assignments': {'a.cfg': assignment}})['assignments']['a.cfg']
    with pytest.raises(ValueError, match='recording profile'):
        metadata_value({'assignments': {'a.cfg': dict(assignment, recording_profile='TB854-approved')}})
