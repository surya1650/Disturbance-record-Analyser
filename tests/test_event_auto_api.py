"""Automatic choices are source-bound, recomputed and distinct from manual inputs."""
from dranalyser.application.worker import Worker
from tests.test_application import environment as environment, payload


def test_automatic_intervals_api_persists_recomputed_evidence_and_manual_override(environment):
    client, app, source, registry = environment
    identity = client.post('/api/intake', files=payload(source)).json()['incident_id']
    Worker(app.state.store, registry).once()
    before = client.get(f'/api/incidents/{identity}').json()
    base = f'/api/incidents/{identity}/event-study'
    response = client.post(base+'/regions', json=dict(revision=1, record='S/event.cfg'))
    assert response.status_code == 200, response.text
    auto = response.json()
    assert auto['status'] == 'selected' and auto['pre'] and auto['fault'] and auto['post']
    assert auto['file'] == 'S/event.cfg' and auto['source_sha256']
    assert auto['intervals']['fault']['start_s'] > auto['intervals']['pre']['last_s']
    assert client.get(f'/api/incidents/{identity}').json() == before
    inputs = dict(same_event_confirmed=False, ends={'S':dict(record='S/event.cfg', substation='Sending',
        timing_mode='auto', pre=[999,1000], fault=[-1,999999], post=None,
        timing_evidence={'method':'Forged certainty','authorizes_location':True})})
    saved = client.put(base, json=dict(revision=1, expected_version=0, inputs=inputs))
    assert saved.status_code == 200, saved.text
    end = saved.json()['inputs']['ends']['S']
    assert end['fault'] == auto['fault'] and end['pre'] == auto['pre'] and end['post'] == auto['post']
    assert end['timing_evidence']['authorizes_location'] is False
    assert end['timing_evidence']['method'] != 'Forged certainty'
    report = client.post(base+'/report', json=dict(revision=1, inputs=saved.json()['inputs']))
    assert report.status_code == 200, report.text
    result = report.json()['ends']['S']
    assert result['timing_mode'] == 'auto' and result['timing_evidence']['boundaries']
    assert len(result['phase_values']) == 6
    assert all(c['pre_rms'] is not None and c['fault_rms'] is not None and c['post_rms'] is not None
               for c in result['phase_values'])
    assert client.get(base, params={'revision':1}).json()['inputs'] == saved.json()['inputs']
    manual = saved.json()['inputs']
    manual['ends']['S'].update(timing_mode='manual', pre=[0,80], fault=[120,180], post=[220,300])
    changed = client.put(base, json=dict(revision=1, expected_version=1, inputs=manual))
    assert changed.status_code == 200, changed.text
    assert changed.json()['inputs']['ends']['S']['fault'] == [120,180]
    assert changed.json()['inputs']['ends']['S']['timing_evidence']['status'] == 'manual'
    assert client.put(base, json=dict(revision=1, expected_version=1, inputs=manual)).status_code == 409
    assert client.post(base+'/regions',json=dict(revision=1,record='../event.cfg')).status_code == 400
    assert client.post(base+'/regions',json=dict(revision=99,record='S/event.cfg')).status_code == 404
    assert client.post(base+'/regions',json=dict(revision=1,record='S/event.cfg',mappings=False)).status_code == 400
