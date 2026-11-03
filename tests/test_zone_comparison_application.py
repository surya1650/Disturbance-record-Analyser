"""Reviewed zone geometry remains source-local, additive and revision-bound."""
import json

import pytest

from dranalyser.application.worker import Worker
from dranalyser.report.zone_comparison_view import render_zone_comparison
from dranalyser.workbench.rx_review import CONFIRMATIONS
from tests import test_application as fixtures
from tests.test_evidence_application import pair_payload
from tests.test_settings import RIO_FIXTURE


environment = fixtures.environment


def export(name, *, wide=True, crlf=False):
    text = RIO_FIXTURE.replace('TRIPCHAR', 'TRIPCHAR-EARTH')
    if wide:
        text = text.replace('6.034', '6000.0').replace('3.500', '3500.0').replace('0.617', '617.0')
    else:
        text = text.replace('6.034', '0.006').replace('3.500', '0.0035').replace('0.617', '0.0006')
    if crlf:
        text = text.replace('\n', '\r\n')
    return ('files', (name, text.encode('latin-1')))


def review(record, **changes):
    value = dict(record_hash=record['content_hash'], settings_hash=record['settings_source']['sha256'],
                 reviewer='Synthetic engineering fixture', reason='Generated data and invented test export only.',
                 ct_ratio=1000, vt_ratio=2500, **dict.fromkeys(CONFIRMATIONS, True))
    return value | changes


def upload(environment, files, assignments, *, line_id=''):
    client, app, _, registry = environment
    response = client.post('/api/intake', files=files, data={'metadata': json.dumps({'assignments': assignments})})
    assert response.status_code == 202, response.text
    identity = response.json()['incident_id']
    worker = Worker(app.state.store, registry)
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    for file in row['bundle']['files']:
        if file['name'] in assignments and file.get('settings_source', {}).get('status') == 'associated export':
            assignments[file['name']]['rx_review'] = review(file)
    response = client.post(f'/api/incidents/{identity}/review', json={
        'revision': 1, 'line_id': line_id, 'assignments': assignments})
    assert response.status_code == 202, response.text
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    assert row['state'] in ('completed', 'attention'), row.get('error')
    return identity, worker, row


def comparisons(client, identity, row):
    navigation = client.get(f'/api/incidents/{identity}/navigator?revision={row["number"]}')
    assert navigation.status_code == 200, navigation.text
    by_file = {record['file']: record['rx']['zone_comparison'] for record in navigation.json()['records']}
    for record in row['result']['relay_evidence']:
        if record['status'] == 'analysed':
            assert record['zone_comparison'] == by_file[record['file']]
            assert record['zone_comparison']['record_hash'] == record['record_hash']
            assert record['zone_comparison']['authorizes_operation'] is False
    json.dumps(by_file, allow_nan=False)
    return by_file


@pytest.mark.parametrize('crlf', [False, True])
def test_reviewed_boundary_is_available_without_line_or_remote_and_same_in_navigator(environment, crlf):
    client, _, source, _ = environment
    name = 'S/event.cfg'
    assignments = {name: {'end': 'S', 'role': 'primary'}}
    identity, _, row = upload(environment, fixtures.payload(source)+[export('S/event.rio', crlf=crlf)], assignments)
    model = comparisons(client, identity, row)[name]
    assert model['status'] == 'available', model['reasons']
    assert model['loop'] == 'AG' and model['characteristic_kind'] == 'earth'
    assert model['window']['evaluated_count'] > 0
    assert model['zones'][0]['status'] == 'inside'
    assert row['result']['location_summary']['accepted'] is False
    html = client.get(f'/api/incidents/{identity}/report?revision=1').text
    assert html.count('data-zone-comparison-version="1"') == 2
    assert 'Fixed operational model window' in html
    assert 'correct protection operation' in html
    assert 'Zone assessment' in html and 'Not assessed' in html


def test_each_corroborating_record_uses_own_settings_and_primary_switch_preserves_models(environment):
    client, _, source, _ = environment
    names = ['S/Main-1/event.cfg', 'S/Main-2/event.cfg']
    files = pair_payload(source, 'S', 'Main-1') + pair_payload(source, 'S', 'Main-2', change=True)
    files += [export('S/Main-1/event.rio'), export('S/Main-2/event.rio', wide=False)]
    assignments = {name: {'end': 'S', 'role': 'primary' if index == 0 else 'corroborating'}
                   for index, name in enumerate(names)}
    identity, worker, row = upload(environment, files, assignments)
    before = comparisons(client, identity, row)
    assert before[names[0]]['zones'][0]['status'] == 'inside'
    assert before[names[1]]['zones'][0]['status'] == 'outside'
    assert before[names[0]]['settings_hash'] != before[names[1]]['settings_hash']
    old_report = client.get(f'/api/incidents/{identity}/report?revision=1').content
    assert client.post(f'/api/incidents/{identity}/reanalyse?revision=1').status_code == 202
    assert worker.once()
    for index, name in enumerate(names):
        assignments[name]['role'] = 'corroborating' if index == 0 else 'primary'
    assert client.post(f'/api/incidents/{identity}/review', json={'revision': 2, 'assignments': assignments}).status_code == 202
    assert worker.once()
    current = client.get(f'/api/incidents/{identity}').json()
    assert comparisons(client, identity, current) == before
    assert client.get(f'/api/incidents/{identity}/report?revision=1').content == old_report


def test_late_settings_and_ambiguous_version_do_not_rewrite_previous_evidence(environment):
    client, _, source, _ = environment
    name = 'S/event.cfg'
    assignments = {name: {'end': 'S', 'role': 'primary'}}
    identity, worker, first = upload(environment, fixtures.payload(source), assignments)
    assert comparisons(client, identity, first)[name]['status'] == 'not_evaluable'
    original = client.get(f'/api/incidents/{identity}/report?revision=1').content
    response = client.post('/api/intake', files=[export('S/event.rio')], data={
        'incident_id': identity, 'expected_revision': '1'})
    assert response.status_code == 202, response.text
    assert worker.once()
    pending = client.get(f'/api/incidents/{identity}').json()
    record = next(file for file in pending['bundle']['files'] if file['name'] == name)
    assignments[name]['rx_review'] = review(record)
    assert client.post(f'/api/incidents/{identity}/review', json={'revision': 2, 'assignments': assignments}).status_code == 202
    assert worker.once()
    second = client.get(f'/api/incidents/{identity}').json()
    assert comparisons(client, identity, second)[name]['status'] == 'available'
    saved = client.get(f'/api/incidents/{identity}/navigator?revision=2').content
    report = client.get(f'/api/incidents/{identity}/report?revision=2').content
    response = client.post('/api/intake', files=[export('S/event-v2.rio', wide=False)], data={
        'incident_id': identity, 'expected_revision': '2',
        'metadata': json.dumps({'auto_analyse': True, 'assignments': assignments})})
    assert response.status_code == 202, response.text
    assert worker.once()
    third = client.get(f'/api/incidents/{identity}').json()
    model = comparisons(client, identity, third)[name]
    assert model['status'] == 'not_evaluable'
    assert model['reasons']
    assert all(zone['evaluated_count'] == 0 for zone in model['zones'])
    assert client.get(f'/api/incidents/{identity}/navigator?revision=2').content == saved
    assert client.get(f'/api/incidents/{identity}/report?revision=2').content == report
    assert client.get(f'/api/incidents/{identity}/report?revision=1').content == original


@pytest.mark.parametrize('stale', ['record_hash', 'settings_hash'])
def test_stale_review_is_named_without_hiding_supported_phase_view(environment, stale):
    client, _, source, _ = environment
    name = 'S/event.cfg'
    assignments = {name: {'end': 'S', 'role': 'primary'}}
    identity, worker, _ = upload(environment, fixtures.payload(source)+[export('S/event.rio')], assignments)
    assert client.post(f'/api/incidents/{identity}/reanalyse?revision=1').status_code == 202
    assert worker.once()
    assignments[name]['rx_review'][stale] = 'f'*64
    assert client.post(f'/api/incidents/{identity}/review', json={'revision': 2, 'assignments': assignments}).status_code == 202
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    model = comparisons(client, identity, row)[name]
    assert model['status'] == 'not_evaluable'
    assert any('stale' in reason.lower() for reason in model['reasons'])
    navigation = client.get(f'/api/incidents/{identity}/navigator?revision=2').json()['records'][0]
    assert navigation['analog'] and navigation['rx']['loops']['AB']


def test_missing_settings_do_not_change_known_two_end_location(environment):
    client, _, source, _ = environment
    assignments = {f'{end}/event.cfg': {'end': end, 'role': 'primary'} for end in ('S', 'R')}
    identity, _, row = upload(environment, fixtures.payload(source)+fixtures.payload(source, 'R'), assignments,
                              line_id='SYNTHETIC-DEMO')
    models = comparisons(client, identity, row)
    assert all(model['status'] == 'not_evaluable' for model in models.values())
    summary = row['result']['location_summary']
    assert summary['accepted'] and summary['method'] == 'E5'
    assert summary['km_from_S'] == pytest.approx(41.98828243177587, abs=1e-10)


def test_technical_view_escapes_model_text_and_never_turns_legacy_or_mismatch_into_outside():
    assert 'Not evaluated in this stored revision' in render_zone_comparison(None)
    assert 'Outside' not in render_zone_comparison({'version': 9, 'status': 'available'})
    assert 'Not evaluated' in render_zone_comparison({'version': True, 'status': 'available'})
    model = dict(version=1, status='available', record_hash='a'*64, settings_hash='b'*64,
                 loop='AG', characteristic_kind='earth', window={}, reasons=['<script>unsafe</script>'], notes=[],
                 zones=[dict(name='<img src=x>', kind='earth', status='inside', inside_count=2,
                             outside_count=0, evaluated_count=2, reasons=[])])
    html = render_zone_comparison(model, 'a'*64)
    assert '<script>' not in html and '<img' not in html
    assert '&lt;script&gt;unsafe&lt;/script&gt;' in html and '&lt;img src=x&gt;' in html
    wrong = render_zone_comparison(model, 'c'*64)
    assert 'does not match this recording' in wrong
    assert 'Inside' not in wrong


def test_navigator_and_annex_share_one_backend_object_per_record(environment, monkeypatch):
    from dranalyser.report import navigation
    from dranalyser.workbench import incident

    client, _, source, _ = environment
    compared, rendered = {}, []
    original_compare, original_render = navigation.compare_zones, incident.render

    def track(*args, **kwargs):
        model = original_compare(*args, **kwargs)
        assert model['record_hash'] not in compared, 'Presentation must not recompute the model.'
        compared[model['record_hash']] = model
        return model

    def check_report(report):
        for record in report.relay_evidence:
            if record['status'] == 'analysed':
                assert record['zone_comparison'] is compared[record['record_hash']]
                rendered.append(record['record_hash'])
        return original_render(report)

    monkeypatch.setattr(navigation, 'compare_zones', track)
    monkeypatch.setattr(incident, 'render', check_report)
    assignments = {f'{end}/event.cfg': {'end': end, 'role': 'primary'} for end in ('S', 'R')}
    identity, _, row = upload(environment, fixtures.payload(source)+fixtures.payload(source, 'R'), assignments)
    comparisons(client, identity, row)
    assert len(compared) == len(rendered) == 2
