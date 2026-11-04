"""Reference choices stay source-bound drafts until explicit applicability review."""
import copy

from dranalyser.application.worker import Worker
from dranalyser.workbench.line_references import reference_line_review
from tests.test_application import environment as environment
from tests.test_incident_inputs import row_and_review
from tests.test_incident_inputs_application import endpoint, inspected


def test_reference_catalog_is_explicit_config_not_an_actual_line_or_default(environment):
    configuration = environment[0].get('/api/config').json()
    catalog = configuration['line_references']
    assert catalog['default_reference_id'] is None and catalog['selection_policy'] == 'explicit-only'
    assert catalog['manual_entry_available']
    assert len(catalog['references']) == 1
    assert all(line['id'] != catalog['references'][0]['id'] for line in configuration['lines'])


def test_unreviewed_reference_saves_same_record_but_calculation_stays_gated(environment):
    identity, before = inspected(environment)
    client, url = endpoint(environment, identity)
    app, registry = environment[1], environment[3]
    _, manual = row_and_review()
    review = dict(manual, **reference_line_review('erpc-2015-powergrid-panther-132-sc'))
    saved = client.post(url, json={'revision': 1, 'review': review})
    assert saved.status_code == 202, saved.text
    assert any('reference applicability' in reason for reason in saved.json()['missing'])
    assert Worker(app.state.store, registry).once()
    draft = app.state.store.get(identity)
    assert draft['files'] == before['files'] and app.state.store.get(identity, 1) == before
    request = dict(revision=2, line_id=draft['metadata']['line_id'], assignments=draft['metadata']['assignments'])
    rejected = client.post(f'/api/incidents/{identity}/review', json=request)
    assert rejected.status_code == 400 and 'reference applicability' in rejected.json()['detail']
    assert app.state.store.get(identity) == draft
    review['reference_reviewed'] = True
    accepted = client.post(url, json={'revision': 2, 'review': review})
    assert accepted.status_code == 202 and not accepted.json()['missing'], accepted.text
    assert Worker(app.state.store, registry).once()
    current = app.state.store.get(identity)
    request.update(revision=3, assignments=current['metadata']['assignments'])
    assert client.post(f'/api/incidents/{identity}/review', json=request).status_code == 202
    assert Worker(app.state.store, registry).once()
    calculated = app.state.store.get(identity)
    # These captures were generated for 220 kV, not this 132 kV reference.
    # Explicit reference review must not bypass the native conformance gate.
    assert calculated['state'] == 'attention', calculated.get('error')
    result = calculated['result']
    assert result['used'] == {} and all('conformance gate' in reason for reason in result['excluded'])
    assert result['location_summary']['km_from_S'] is None
    assert result['line_snapshot']
    assert calculated['files'] == before['files'] and app.state.store.get(identity, 2) == draft


def test_api_refuses_false_reference_label_without_mutating_incident(environment):
    identity, before = inspected(environment)
    client, url = endpoint(environment, identity)
    _, manual = row_and_review()
    review = dict(manual, **reference_line_review('erpc-2015-powergrid-panther-132-sc'))
    review['x1'] = .4
    original = copy.deepcopy(review)
    rejected = client.post(url, json={'revision': 1, 'review': review})
    assert rejected.status_code == 400 and 'constants changed' in rejected.json()['detail']
    assert review == original and environment[1].state.store.get(identity) == before
