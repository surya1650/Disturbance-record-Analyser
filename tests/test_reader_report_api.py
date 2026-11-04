"""Reader report generations remain immutable across edits, reruns and revisions."""
import copy
import json

import pytest

from dranalyser.application import incident_report as reports
from dranalyser.application.worker import Worker
from tests import test_application as fixtures
from tests.test_application import payload

environment = fixtures.environment


def incident(environment, *, automatic=False):
    client, app, source, registry = environment
    data = {'metadata': (source / 'intake.json').read_text()} if automatic else {}
    files = payload(source) + (payload(source, 'R') if automatic else [])
    identity = client.post('/api/intake', files=files, data=data).json()['incident_id']
    assert Worker(app.state.store, registry).once()
    return identity, app.state.store.get(identity)


@pytest.fixture
def model_adapter(monkeypatch):
    calls = []

    def build(root, row, records, event_inputs):
        calls.append(dict(row=copy.deepcopy(row), records=records, event_inputs=copy.deepcopy(event_inputs)))
        return dict(version=1, incident_id=row['incident_id'], revision=row['number'],
                    records=records or ['S/event.cfg'], summary='Recorded observations', pages=4)

    monkeypatch.setattr(reports, '_build_model', build)
    monkeypatch.setattr(reports, '_render_model', lambda model: '<!DOCTYPE html><p>'+model['summary']+'</p>')
    return calls


def test_report_generations_keep_old_outputs_and_operational_report_unchanged(environment, model_adapter):
    client, app, _, _ = environment
    identity, before = incident(environment, automatic=True)
    legacy = client.get(f'/api/incidents/{identity}/report?revision=1').content
    base = f'/api/incidents/{identity}/incident-report'
    assert client.get(base+'?revision=1').json()['report'] is None
    first = client.post(base, json={'revision': 1}).json()
    assert first['is_current'] and first['revision'] == 1
    assert first['model']['generation']['timezone'] == 'Asia/Calcutta'
    original = client.get(first['urls']['data']).content
    html = client.get(first['urls']['html']).content
    second = client.post(base, json={'revision': 1, 'records': ['R/event.cfg']}).json()
    assert second['report_id'] != first['report_id']
    assert client.get(base+'?revision=1').json()['report_id'] == second['report_id']
    assert [item['report_id'] for item in second['history']] == [second['report_id'], first['report_id']]
    assert client.get(second['history'][1]['urls']['html']).content == html
    assert client.get(first['urls']['data']).content == original
    assert client.get(first['urls']['html']).content == html
    assert client.get(f'/api/incidents/{identity}/report?revision=1').content == legacy
    assert app.state.store.get(identity)['result'] == before['result']
    assert app.state.store.get(identity)['files'] == before['files']
    assert model_adapter[-1]['records'] == ['R/event.cfg']
    assert 'attachment;' in client.get(first['urls']['html']+'?download=true').headers['content-disposition']
    assert 'attachment;' in client.get(first['urls']['data']+'?download=true').headers['content-disposition']


def test_saved_manual_regions_reach_builder_and_mark_previous_generation_stale(environment, model_adapter):
    client, _, _, _ = environment
    identity, _ = incident(environment)
    event = f'/api/incidents/{identity}/event-study'
    values = dict(same_event_confirmed=False, ends={'S': dict(record='S/event.cfg', substation='Synthetic',
        timing_mode='manual', pre=[0, 80], fault=[130, 190], post=[230, 300],
        relay_distance=None, mappings={}, asserted_states={})})
    saved = client.put(event, json=dict(revision=1, expected_version=0, inputs=values))
    assert saved.status_code == 200, saved.text
    base = f'/api/incidents/{identity}/incident-report'
    report = client.post(base, json={'revision': 1}).json()
    assert model_adapter[-1]['event_inputs']['version'] == 1
    assert model_adapter[-1]['event_inputs']['inputs']['ends']['S']['fault'] == [130, 190]
    original = client.get(report['urls']['data']).content
    values['ends']['S']['fault'] = [140, 200]
    assert client.put(event, json=dict(revision=1, expected_version=1, inputs=values)).status_code == 200
    assert not client.get(base+'?revision=1').json()['is_current']
    assert client.get(report['urls']['data']).content == original
    updated = client.post(base, json={'revision': 1}).json()
    assert updated['is_current']
    assert model_adapter[-1]['event_inputs']['version'] == 2


@pytest.mark.parametrize('change', ['metadata', 'revision'])
def test_inputs_changing_during_generation_cannot_publish_stale_report(environment, model_adapter, monkeypatch, change):
    client, app, source, _ = environment
    identity, row = incident(environment)
    original_build = reports._build_model

    def racing_build(*args):
        model = original_build(*args)
        if change == 'metadata':
            with app.state.store.connect() as db:
                db.execute('UPDATE revisions SET metadata=? WHERE id=?', (json.dumps({'changed': True}), row['id']))
        else:
            app.state.store.submit(name=row['name'], source='manual', files=row['files'], metadata={},
                fingerprint='newer-during-report', incident_id=identity, expected=1)
        return model

    monkeypatch.setattr(reports, '_build_model', racing_build)
    response = client.post(f'/api/incidents/{identity}/incident-report', json={'revision': 1})
    assert response.status_code == 409 and 'changed' in response.text
    with app.state.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM reader_reports').fetchone()[0] == 0
    folder = app.state.store.root / 'runs' / identity / '1' / 'reader-reports'
    assert not list(folder.iterdir())
    assert (source / 'S/event.dat').is_file()


def test_report_artifacts_are_incident_scoped_and_changed_files_are_not_served(environment, model_adapter):
    client, app, _, _ = environment
    identity, _ = incident(environment)
    report = client.post(f'/api/incidents/{identity}/incident-report', json={'revision': 1}).json()
    assert client.get(report['urls']['html'].replace(identity, 'f'*32)).status_code == 404
    assert client.get(f'/api/incidents/{identity}/incident-report/not-a-report/html').status_code == 404
    path = app.state.store.root / 'runs' / identity / '1' / 'reader-reports' / report['report_id'] / 'report.html'
    path.write_text('modified artifact', encoding='utf-8')
    assert client.get(report['urls']['html']).status_code == 404
    assert client.get(report['urls']['data']).status_code == 200
    assert client.get(f'/api/incidents/{identity}/incident-report?revision=1').status_code == 404


@pytest.mark.parametrize('records', [[], ['S/event.cfg']*2, ['../event.cfg'], ['S/event.dat'], ['other.cfg']])
def test_report_rejects_invalid_or_cross_source_selection(environment, model_adapter, records):
    client, _, _, _ = environment
    identity, _ = incident(environment)
    response = client.post(f'/api/incidents/{identity}/incident-report', json={'revision': 1, 'records': records})
    assert response.status_code == 400
    assert not model_adapter


def test_generation_requires_write_token_and_completed_parsing(environment, model_adapter):
    client, app, source, _ = environment
    identity = client.post('/api/intake', files=payload(source)).json()['incident_id']
    base = f'/api/incidents/{identity}/incident-report'
    assert client.post(base, json={'revision': 1}).status_code == 409
    client.headers.pop('X-DR-Token')
    assert client.post(base, json={'revision': 1}).status_code == 401
    assert not model_adapter
    with app.state.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM reader_reports').fetchone()[0] == 0


@pytest.mark.parametrize('paired', [False, True])
def test_real_source_report_generates_without_optional_physical_inputs(environment, paired):
    client, app, _, _ = environment
    identity, before = incident(environment, automatic=paired)
    base = f'/api/incidents/{identity}/incident-report'
    legacy = client.get(f'/api/incidents/{identity}/report?revision=1').content if paired else None
    response = client.post(base, json={'revision': 1})
    assert response.status_code == 201, response.text
    first = response.json()
    model = first['model']
    assert model['kind'] == 'incident-reader-report' and model['version'] == 1
    assert model['line_diagram']['version'] == 1
    assert len(model['sources']) == (2 if paired else 1)
    assert all(len(source['phase_values']) == 6 for source in model['sources'])
    assert all(source['source_sha256'] for source in model['sources'])
    if paired:
        assert model['location']['method'] == 'E5'
        assert model['line_diagram']['line']['length_km'] == 100
        assert model['line_diagram']['fault']['method'] == 'E5'
        assert model['line_diagram']['terminals']['S']['label'] == 'Synthetic S'
        assert model['location']['km_from_S'] == pytest.approx(41.98828243177587, abs=1e-10)
        assert client.get(f'/api/incidents/{identity}/report?revision=1').content == legacy
    else:
        assert model['location']['km_from_S'] is None
        assert model['location']['reason']
    original = client.get(first['urls']['data']).content
    html = client.get(first['urls']['html']).content
    assert html.count(b'class="page"') == 4
    assert b'<svg' in html and b'window.print()' in html
    assert b'class="line-diagram"' in html
    second = client.post(base, json={'revision': 1})
    assert second.status_code == 201, second.text
    assert second.json()['report_id'] != first['report_id']
    assert len(second.json()['history']) == 2
    assert client.get(first['urls']['data']).content == original
    assert client.get(first['urls']['html']).content == html
    after = app.state.store.get(identity)
    assert after['files'] == before['files']
    assert after['metadata'] == before['metadata']
    assert after['result'] == before['result']
