"""Manual identities and diagram declarations never change numerical assignments."""
import pytest

from dranalyser.application.worker import Worker
from tests.test_application import environment as environment, payload


def upload(environment):
    client, app, source, registry = environment
    identity = client.post('/api/intake', files=payload(source)+payload(source, 'R')).json()['incident_id']
    Worker(app.state.store, registry).once()
    return identity, f'/api/incidents/{identity}'


def test_end_labels_are_explicit_persistent_escaped_and_revision_scoped(environment):
    client, app, source, registry = environment
    identity, base = upload(environment)
    before = client.get(base).json()
    blank = client.get(base+'/end-names?revision=1').json()
    assert blank['record_ends'] == {'S/event.cfg': '', 'R/event.cfg': ''}
    assert blank['names'] == {'S': '', 'R': ''}
    body = dict(revision=1, version=0, names={'S': '<b>Sending SS</b>', 'R': 'Receiving SS'},
                record_ends={'S/event.cfg': 'S', 'R/event.cfg': 'S'})
    response = client.put(base+'/end-names', json=body)
    assert response.status_code == 200, response.text
    assert response.json()['record_ends']['R/event.cfg'] == 'S'  # names never use upload order
    assert client.get(base).json() == before
    assert client.put(base+'/end-names', json=body).status_code == 409
    assert client.put(base+'/end-names', json=dict(body, version=1, record_ends={'missing.cfg': 'R'})).status_code == 400
    assert client.put(base+'/end-names', json=dict(body, version=1, names={'S': 'bad\nname'})).status_code == 400
    reopened = type(app.state.store)(app.state.store.root)
    assert reopened.get(identity)['metadata'] == before['metadata']
    assert client.post('/api/intake', files=[('files', ('notes.txt', b'Additional incident evidence'))], data={'incident_id': identity, 'expected_revision': '1'}).status_code == 202
    Worker(app.state.store, registry).once()
    inherited = client.get(base+'/end-names?revision=2').json()
    assert inherited['names']['S'] == '<b>Sending SS</b>'
    assert inherited['version'] == 0
    update = dict(body, revision=2, names={'S': 'New sending SS', 'R': ''})
    assert client.put(base+'/end-names', json=update).status_code == 200
    assert client.get(base+'/end-names?revision=1').json()['names']['S'] == '<b>Sending SS</b>'


def test_operational_names_follow_frozen_line_and_archived_report_is_unchanged(environment):
    client, app, source, registry = environment
    identity, base = upload(environment)
    body = dict(revision=1, version=0, names={'S': '<script>test</script>', 'R': 'Manual SS'},
                record_ends={'S/event.cfg': 'S', 'R/event.cfg': 'R'})
    assert client.put(base+'/end-names', json=body).status_code == 200
    response = client.post(base+'/review', json=dict(revision=1, line_id='SYNTHETIC-DEMO', assignments={
        'S/event.cfg': {'end': 'S', 'role': 'primary'}, 'R/event.cfg': {'end': 'R', 'role': 'primary'}}))
    assert response.status_code == 202, response.text
    Worker(app.state.store, registry).once()
    names = client.get(base+'/end-names?revision=1').json()
    assert names['name_sources'] == {'S': 'line definition', 'R': 'line definition'}
    archived = client.get(base+'/report?revision=1').content
    named = client.get(base+'/named-report?revision=1').text
    assert 'Sending end' in named and names['names']['S'] in named
    assert client.get(base+'/report?revision=1').content == archived
    bad = dict(body, version=1, record_ends={'S/event.cfg': 'R'})
    assert client.put(base+'/end-names', json=bad).status_code == 400
    assert client.put(base+'/end-names', json=dict(body, version=1, names={'S': 'Other'})).status_code == 200
    assert client.get(base+'/end-names?revision=1').json()['names'] == names['names']
    assert client.get(base+'/report?revision=1').content == archived


def declarations():
    return dict(reviewer='Synthetic test', evidence='Known synthetic source basis, not field data',
                primary_scaling_confirmed=True, zone_basis='secondary', ct_ratio=1000, vt_ratio=2000,
                zones=[dict(name='Phase Z1', shape='mho', reach=10, angle=75, points=[])])


def test_manual_names_are_escaped_in_report_without_line_definition(environment):
    client, app, source, registry = environment
    identity, base = upload(environment)
    client.put(base+'/end-names', json=dict(revision=1, version=0, names={'S': '<script>unsafe()</script>', 'R': 'Other SS'}, record_ends={}))
    response = client.post(base+'/review', json=dict(revision=1, line_id='', assignments={
        'S/event.cfg': {'end': 'S', 'role': 'primary'}, 'R/event.cfg': {'role': 'excluded', 'end': ''}}))
    assert response.status_code == 202, response.text
    Worker(app.state.store, registry).once()
    original = client.get(base+'/report?revision=1')
    assert original.status_code == 200
    named = client.get(base+'/named-report?revision=1&download=true')
    assert named.status_code == 200
    assert '<script>unsafe()</script>' not in named.text
    assert '&lt;script&gt;unsafe()&lt;/script&gt;' in named.text
    assert 'attachment' in named.headers['Content-Disposition']
    assert client.get(base+'/report?revision=1').content == original.content


def test_diagram_inputs_are_source_scoped_validated_and_survive_reload(environment):
    client, app, source, registry = environment
    identity, base = upload(environment)
    before = client.get(base).json()
    query = '?revision=1&record=S/event.cfg'
    initial = client.get(base+'/diagram-inputs'+query).json()
    assert initial['version'] == 0 and initial['options'] is None
    choices = dict(voltage_kv=0, mappings={'A1': 'IA'}, line_model=dict(name='Manual line', length_km=100, x1_ohm_per_km=.4), fault_loop='AB')
    body = dict(revision=1, record='S/event.cfg', version=0, options=choices, diagram=declarations())
    result = client.put(base+'/diagram-inputs', json=body)
    assert result.status_code == 200, result.text
    assert result.json() == client.get(base+'/diagram-inputs'+query).json()
    assert result.json()['options']['line_model']['length_km'] == 100
    assert client.get(base+'/diagram-inputs?revision=1&record=R/event.cfg').json()['options'] is None
    assert client.get(base).json() == before
    assert client.put(base+'/diagram-inputs', json=body).status_code == 409
    body['version'] = 1
    body['diagram']['zones'] = [dict(name='Declared polygon', shape='polygon', reach=None, angle=None, points=[[0, 0], [10, 0], [10, 30], [0, 30]])]
    assert client.put(base+'/diagram-inputs', json=body).status_code == 200
    assert client.get(base+'/diagram-inputs?revision=1&record=missing.cfg').status_code == 400
    assert client.put(base+'/diagram-inputs', json=dict(body, record='@join:["S/event.cfg","R/event.cfg"]')).status_code == 400


@pytest.mark.parametrize('change', [
    {'reviewer': ''}, {'zone_basis': 'guessed'}, {'ct_ratio': 0}, {'vt_ratio': -1},
    {'primary_scaling_confirmed': 'yes'}, {'zones': [{}]},
    {'zones': [dict(name='Missing angle', shape='mho', reach=20, angle=None, points=[])]},
    {'zones': [dict(name='Too few', shape='polygon', reach=None, angle=None, points=[[0, 0], [1, 1]])]},
])
def test_bad_diagram_inputs_do_not_replace_saved_values(environment, change):
    client, app, source, registry = environment
    identity, base = upload(environment)
    body = dict(revision=1, record='S/event.cfg', version=0, options={}, diagram=declarations()|change)
    response = client.put(base+'/diagram-inputs', json=body)
    assert response.status_code == 400, response.text
    assert client.get(base+'/diagram-inputs?revision=1&record=S/event.cfg').json()['version'] == 0
    assert client.get(base).json()['metadata']['assignments'] == {}
