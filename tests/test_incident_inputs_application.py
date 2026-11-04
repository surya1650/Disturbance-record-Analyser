"""Saved line facts stay with exact captures on immutable incident revisions."""
import copy

from dranalyser.application.incident_inputs import install_incident_inputs
from dranalyser.application.worker import Worker
from tests.test_application import environment as environment, payload
from tests.test_incident_inputs import row_and_review
from tests.test_instrument_review import upload_missing_ratios


def endpoint(environment, identity):
    client, app, _, _ = environment
    path = '/api/incidents/{incident_id}/line-inputs'
    if not any(getattr(route, 'path', '') == path for route in app.routes):
        install_incident_inputs(app, app.state.store)
    return client, f'/api/incidents/{identity}/line-inputs'


def inspected(environment, both=True):
    client, app, source, registry = environment
    response = client.post('/api/intake', files=payload(source)+(payload(source, 'R') if both else []),
        data={'name': 'Synthetic incident line review'})
    assert response.status_code == 202, response.text
    identity = response.json()['incident_id']
    assert Worker(app.state.store, registry).once()
    return identity, app.state.store.get(identity)


def test_partial_line_facts_create_same_incident_revision_with_original_files(environment):
    identity, before = inspected(environment)
    client, url = endpoint(environment, identity)
    app, registry = environment[1], environment[3]
    original_bytes = {f['sha256']: (app.state.intake.blobs/f['sha256']).read_bytes() for f in before['files']}
    initial = client.get(url, params={'revision': 1})
    assert initial.status_code == 200 and initial.json()['review'] is None
    response = client.post(url, json={'revision': 1, 'review': {'length_km': 83}})
    assert response.status_code == 202, response.text
    assert response.json()['revision'] == 2 and response.json()['incident_id'] == identity
    assert response.json()['missing']
    assert Worker(app.state.store, registry).once()
    current = app.state.store.get(identity)
    saved = client.get(url, params={'revision': 2}).json()
    assert saved['review']['length_km'] == 83 and saved['review']['kv'] is None
    assert saved['review']['r1'] is None and saved['review']['ends'] == {}
    assert current['state'] == 'needs_review' and current['files'] == before['files']
    assert current['name'] == before['name'] and len(app.state.store.list()) == 1
    assert app.state.store.get(identity, 1) == before
    assert {f['sha256']: (app.state.intake.blobs/f['sha256']).read_bytes() for f in current['files']} == original_bytes
    assert {f['name'] for f in current['bundle']['files']} == {f['name'] for f in before['bundle']['files']}
    assert client.get(url, params={'revision': 1}).json()['review'] is None


def test_complete_two_end_line_review_needs_no_zero_sequence_source_or_gps_inputs(environment):
    identity, before = inspected(environment)
    client, url = endpoint(environment, identity)
    app, registry = environment[1], environment[3]
    _, review = row_and_review()
    response = client.post(url, json={'revision': 1, 'review': review})
    assert response.status_code == 202 and not response.json()['missing'], response.text
    assert Worker(app.state.store, registry).once()
    row = app.state.store.get(identity)
    assert row['metadata']['incident_line']['review']['r0'] is None
    # Assignment edits cannot silently reinterpret which sources supply the reviewed physical ends.
    swapped = copy.deepcopy(row['metadata']['assignments'])
    swapped['S/event.cfg']['end'], swapped['R/event.cfg']['end'] = 'R', 'S'
    rejected = client.post(f'/api/incidents/{identity}/review', json={'revision': 2,
        'line_id': row['metadata']['line_id'], 'assignments': swapped})
    assert rejected.status_code == 400 and 'physical ends differ' in rejected.json()['detail']
    assert app.state.store.get(identity) == row
    response = client.post(f'/api/incidents/{identity}/review', json={'revision': 2,
        'line_id': row['metadata']['line_id'], 'assignments': row['metadata']['assignments']})
    assert response.status_code == 202, response.text
    assert Worker(app.state.store, registry).once()
    after = app.state.store.get(identity)
    assert after['state'] == 'completed', after.get('error')
    assert after['result']['used'] == {'S': 'S/event.cfg', 'R': 'R/event.cfg'}
    assert 'E5' in after['result']['location_text']
    assert after['files'] == before['files'] and app.state.store.get(identity, 1) == before
    assert client.get(f'/api/incidents/{identity}/report?revision=2').status_code == 200


def test_line_revision_preserves_same_record_instrument_review_and_can_be_edited(environment):
    client, app, registry, identity, before, name, instrument_review = upload_missing_ratios(environment)
    response = client.post(f'/api/incidents/{identity}/instrument-review',
        json=dict(record=name, revision=1, review=instrument_review, save=True))
    assert response.status_code == 200, response.text
    assert Worker(app.state.store, registry).once()
    ratio_revision = app.state.store.get(identity)
    client, url = endpoint(environment, identity)
    _, review = row_and_review()
    review['ends'].pop('R')
    review['confirmed_same_event'] = False
    response = client.post(url, json={'revision': 2, 'review': review})
    assert response.status_code == 202 and not response.json()['missing'], response.text
    assert Worker(app.state.store, registry).once()
    first = app.state.store.get(identity)
    assert first['metadata']['assignments'][name]['instrument_review'] == instrument_review
    assert first['files'] == before['files']
    assert app.state.store.get(identity, 2) == ratio_revision
    review['length_km'] = 101
    review['ends']['S']['name'] = 'Edited synthetic station'
    response = client.post(url, json={'revision': 3, 'review': review})
    assert response.status_code == 202 and response.json()['revision'] == 4, response.text
    assert Worker(app.state.store, registry).once()
    latest = app.state.store.get(identity)
    assert latest['metadata']['assignments'][name]['instrument_review'] == instrument_review
    assert latest['files'] == before['files'] and app.state.store.get(identity, 3) == first
    saved = client.get(url, params={'revision': 4}).json()['review']
    assert saved['length_km'] == 101 and saved['ends']['S']['name'] == 'Edited synthetic station'


def test_revision_and_source_guards_refuse_changes_without_creating_history(environment):
    client, app, source, registry = environment
    response = client.post('/api/intake', files=payload(source))
    identity = response.json()['incident_id']
    client, url = endpoint(environment, identity)
    assert client.post(url, json={'revision': 1, 'review': {}}).status_code == 409
    assert Worker(app.state.store, registry).once()
    before = app.state.store.get(identity)
    for body in ({'revision': True, 'review': {}}, {'revision': 0, 'review': {}},
                 {'revision': 1, 'review': None}, {'revision': 1, 'review': {}, 'source_sha256': {}},
                 {'revision': 1, 'review': {'ends': {'S': {'record': 'other.cfg'}}}},
                 {'revision': 1, 'review': {'kv': -1}},
                 {'revision': 1, 'review': {'ends': {'S': {'record': '../event.cfg'}}}}):
        rejected = client.post(url, json=body)
        assert rejected.status_code == 400, rejected.text
        assert app.state.store.get(identity) == before
    assert client.get(url).status_code == 422
    assert client.get(url, params={'revision': 99}).status_code == 404
    assert client.get('/api/incidents/'+'f'*32+'/line-inputs?revision=1').status_code == 404
    assert client.post(url, json={'revision': 1, 'review': {}}).status_code == 202
    assert Worker(app.state.store, registry).once()
    latest = app.state.store.get(identity)
    assert client.post(url, json={'revision': 1, 'review': {'kv': 220}}).status_code == 409
    assert app.state.store.get(identity) == latest
    assert len(app.state.store.history(identity)['revisions']) == 2
