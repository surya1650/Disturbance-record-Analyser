"""Per-record R-X declarations survive revisions and never promote advisory audits."""
import json

from dranalyser.application.worker import Worker
from tests import test_application as fixtures
from tests.test_evidence_application import pair_payload
from tests.test_rx_review import inputs
from tests.test_settings import RIO_FIXTURE

environment = fixtures.environment


def test_rx_review_is_per_record_stale_settings_withhold_curves_and_old_reports_are_frozen(environment):
    client, app, source, registry = environment
    names = ['S/Main-1/event.cfg', 'S/Main-2/event.cfg']
    assignments = {name: {'end': 'S', 'role': 'primary' if i == 0 else 'corroborating',
                          'protection_system': 'Main-'+str(i+1)} for i, name in enumerate(names)}
    files = pair_payload(source, 'S', 'Main-1') + pair_payload(source, 'S', 'Main-2', change=True)
    files.append(('files', ('S/Main-1/event.rio', RIO_FIXTURE.encode())))
    response = client.post('/api/intake', files=files, data={'metadata': json.dumps({'assignments': assignments})})
    identity = response.json()['incident_id']
    worker = Worker(app.state.store, registry)
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    assert row['state'] == 'needs_review'
    record = next(f for f in row['bundle']['files'] if f['name'] == names[0])
    assert record['settings_source']['status'] == 'associated export'
    review = inputs()[3] | {'record_hash': record['content_hash'],
                            'settings_hash': record['settings_source']['sha256'],
                            'reason': 'Synthetic only <script>alert(1)</script>'}
    assignments[names[0]]['rx_review'] = review
    assert client.post(f'/api/incidents/{identity}/review', json={'revision': 1, 'assignments': assignments}).status_code == 202
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    assert row['state'] == 'completed', row.get('error')
    first = client.get(f'/api/incidents/{identity}/navigator?revision=1').content
    records = {r['file']: r for r in json.loads(first)['records']}
    assert 'AG' in records[names[0]]['rx']['loops']
    assert 'AG' not in records[names[1]]['rx']['loops']
    assert records[names[0]]['rx']['zones']['phase']
    assert not records[names[0]]['rx']['zones']['earth']  # no fallback from phase
    assert all(next(c for c in a['settings_checks'] if c['id'] == 'SET-VALIDITY')['status'] == 'not_evaluable'
               for a in row['result']['standards_audits'])
    report = client.get(f'/api/incidents/{identity}/report?revision=1').content
    assert b'Ground-loop and zone input evidence' in report
    assert b'&lt;script&gt;alert(1)&lt;/script&gt;' in report
    assert b'<script>alert(1)</script>' not in report
    # Intake never overwrites old files. A second settings version makes the
    # association ambiguous and must withhold the previously reviewed display.
    response = client.post('/api/intake', files=[('files', ('S/Main-1/event-v2.rio', (RIO_FIXTURE+'\nFEEDER NEW VERSION').encode()))],
                           data={'incident_id': identity, 'expected_revision': 1,
                                 'metadata': json.dumps({'assignments': assignments, 'auto_analyse': True})})
    assert response.status_code == 202
    assert worker.once()
    records = client.get(f'/api/incidents/{identity}/navigator?revision=2').json()['records']
    main1 = next(r for r in records if r['file'] == names[0])
    assert 'AG' not in main1['rx']['loops'] and not main1['rx']['zones']['phase']
    assert any('stale' in why for why in main1['rx']['context']['ground_missing'])
    assert client.get(f'/api/incidents/{identity}/navigator?revision=1').content == first
    assert client.get(f'/api/incidents/{identity}/report?revision=1').content == report
