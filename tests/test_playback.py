"""Playback preserves missing evidence, exact source brackets and end identity."""
import shutil
import subprocess
from pathlib import Path

import pytest

from dranalyser.application.worker import Worker
from dranalyser.workbench.playback import signal_timeline, duration
from tests.test_application import environment as environment, payload


def settings(ends=('S',)):
    return dict(alignment='independent', common_event=len(ends) == 2, reviewer='Synthetic reviewer', evidence='Synthetic fixture identities and indications',
                ends={end: dict(record=f'{end}/event.cfg', offset_ms=0, onset_ms=None, signals_reviewed=True,
                                signals={'trip': dict(id='D2', active=1), 'open': dict(id='D4', active=1)}) for end in ends})


def upload(env):
    client, app, source, registry = env
    identity = client.post('/api/intake', files=payload(source)+payload(source, 'R')).json()['incident_id']
    assert Worker(app.state.store, registry).once()
    return identity, f'/api/incidents/{identity}/playback'


def test_signal_brackets_initial_states_gaps_unknowns_and_resource_budget():
    out = signal_timeline([1, 1, 0, 1, None, 1, 0, 1], [0, .001, .002, .003, .004, .005, 1, 1.001], 1)
    assert [e['index'] for e in out['edges']] == [3, 7]
    assert out['edges'][0]['bracket_s'] == [.002, .003]
    assert out['runs'][0] == [0, .002, 1]
    assert any(r[2] is None for r in out['runs'])
    assert out['runs'][-2][0] == 1
    zero = signal_timeline([1, 0, 1, 0], [0, 1, 2, 3], 0)
    assert [e['index'] for e in zero['edges']] == [1, 3]
    boundary = signal_timeline([0, 1, 0, 1], [0, 1, 2, 3], 1, [1])
    assert [e['index'] for e in boundary['edges']] == [3]
    excessive = signal_timeline([i % 2 for i in range(5000)], list(range(5000)), 1)
    assert excessive['status'] == 'unavailable' and not excessive['runs'] and not excessive['edges']
    assert duration(None, zero['edges'][0]) is None
    measured = duration(zero['edges'][0], zero['edges'][1])
    assert measured == dict(ms=2000, sample_bracket_ms=[1000, 3000])


def test_playback_source_bound_versioned_and_does_not_change_reports_or_assignments(environment):
    client, app, source, registry = environment
    identity, base = upload(environment)
    before = client.get(f'/api/incidents/{identity}').json()
    assert client.get(base+'?revision=1').json()['settings'] is None
    assert client.get(base+'/data?revision=1').status_code == 404
    raw = dict(revision=1, version=0, settings=settings(('S', 'R')))
    response = client.put(base, json=raw)
    assert response.status_code == 200, response.text
    assert client.put(base, json=raw).status_code == 409
    data = client.get(base+'/data?revision=1')
    assert data.status_code == 200, data.text
    model = data.json()
    assert model['alignment_eligible'] is model['authorizes_location'] is False
    assert len(model['records']) == 2
    for rec in model['records']:
        assert rec['source_sha256'] and rec['signals']['open']['edges']
        assert rec['timings']['trip_to_open']['ms'] > 0
        assert rec['timings']['fault_to_trip'] is None
        assert rec['timings']['open_to_closed'] is None
        assert len(rec['ar_sequences']) == 1
        assert rec['ar_sequences'][0]['closed_s'] is None
        assert rec['ar_sequences'][0]['closed_to_retrip'] is None
        assert len(rec['analog']) == 6 and rec['analog_omitted'] == 2
    assert client.get(f'/api/incidents/{identity}').json() == before
    assert client.post('/api/intake', files=[('files', ('note.txt', b'new evidence'))], data={'incident_id': identity, 'expected_revision': 1}).status_code == 202
    Worker(app.state.store, registry).once()
    assert client.get(base+'?revision=2').json()['settings'] is None
    assert client.get(base+'/data?revision=1').json() == model


@pytest.mark.parametrize('case', ['common', 'duplicate', 'polarity', 'mapping', 'same_signal', 'offset', 'onset', 'no_review', 'huge_number', 'bad_id', 'record_type'])
def test_unsafe_playback_inputs_fail_without_saving(environment, case):
    client, app, source, registry = environment
    identity, base = upload(environment)
    raw = settings(('S', 'R'))
    s = raw['ends']['S']
    if case == 'common':
        raw['common_event'] = False
    if case == 'duplicate':
        raw['ends']['R']['record'] = s['record']
    if case == 'polarity':
        s['signals']['open']['active'] = True
    if case == 'mapping':
        s['signals_reviewed'] = False
    if case == 'same_signal':
        s['signals']['open'] = s['signals']['trip']
    if case == 'offset':
        s['offset_ms'] = 100
    if case == 'onset':
        s['onset_ms'] = 1e10
    if case == 'no_review':
        raw['evidence'] = ''
    if case == 'huge_number':
        s['offset_ms'] = 10**500
    if case == 'bad_id':
        s['signals']['open']['id'] = []
    if case == 'record_type':
        s['record'] = []
    response = client.put(base, json=dict(revision=1, version=0, settings=raw))
    assert response.status_code == 400, response.text
    assert client.get(base+'?revision=1').json()['version'] == 0


def test_end_label_changes_invalidate_saved_playback_and_csrf_is_enforced(environment):
    client, app, source, registry = environment
    identity, base = upload(environment)
    body = dict(revision=1, version=0, settings=settings())
    assert client.put(base, json=body, headers={'X-DR-Token': 'wrong'}).status_code == 401
    assert client.put(base, json=body).status_code == 200
    assert client.put(f'/api/incidents/{identity}/end-names', json=dict(revision=1, version=0, names={}, record_ends={'S/event.cfg': 'R'})).status_code == 200
    assert client.get(base+'/data?revision=1').status_code == 409
    assert client.put(base, json={**body, 'version': 1}).status_code == 400


def test_same_declared_relay_captures_cannot_be_used_as_opposite_ends(environment):
    client, app, source, registry = environment
    s = (source/'S/event.cfg').read_text().splitlines()[0]
    path = source/'R/event.cfg'
    lines = path.read_text().splitlines()
    lines[0] = s
    path.write_text('\n'.join(lines)+'\n')
    identity, base = upload(environment)
    response = client.put(base, json=dict(revision=1, version=0, settings=settings(('S', 'R'))))
    assert response.status_code == 400 and 'same station and relay' in response.text


def test_playback_clock_contact_and_request_models():
    subprocess.run([shutil.which('node'), str(Path(__file__).with_name('playback.cjs'))], check=True)


def test_large_capture_is_compressed_and_initial_assertion_has_no_invented_time():
    size = 200000
    out = signal_timeline([1]*size, [i/2000 for i in range(size)], 1)
    assert len(out['runs']) == 1 and out['edges'] == []


def test_declared_line_length_is_available_without_promoting_a_fault_location(environment):
    client, app, source, registry = environment
    identity, base = upload(environment)
    assert client.put(base, json=dict(revision=1, version=0, settings=settings(('S', 'R')))).status_code == 200
    custom = dict(options={'line_model': {'name': 'Declared test line', 'length_km': 123, 'x1_ohm_per_km': .4}}, diagram={})
    assert client.put(f'/api/incidents/{identity}/diagram-inputs', json=dict(revision=1, version=0, record='S/event.cfg', **custom)).status_code == 200
    data = client.get(base+'/data?revision=1').json()
    assert data['line']['length_km'] == 123
    assert data['source_inputs']['S/event.cfg']['version'] == 1
    assert data['source_inputs']['S/event.cfg']['options']['line_model']['length_km'] == 123
    assert not data['line']['location'].get('overlay_eligible')
    custom['options']['line_model']['length_km'] = 321
    assert client.put(f'/api/incidents/{identity}/diagram-inputs', json=dict(revision=1, version=0, record='R/event.cfg', **custom)).status_code == 200
    data = client.get(base+'/data?revision=1').json()
    assert data['line']['length_km'] is None and 'Conflicting' in data['line']['provenance']


def test_huge_revision_returns_input_error_instead_of_database_overflow(environment):
    client, app, source, registry = environment
    identity, base = upload(environment)
    assert client.get(f'/api/incidents/{identity}?revision='+str(10**500)).status_code == 400


@pytest.mark.parametrize('points,valid', [
    ([[0, 0], [10, 0], [10, 30], [0, 30]], True),
    ([[0, 0], [10, 0], [10, 30], [0, 30], [0, 0]], True),
    ([[0, 0], [1, 1], [2, 2]], False),
    ([[0, 0], [10, 10], [10, 0], [0, 10]], False),
    ([[0, 0], [10, 0], [5, 0], [5, 5]], False),
])
def test_declared_zone_geometry_rejects_degenerate_and_crossed_outlines(points, valid):
    from dranalyser.application.diagram_inputs import clean_diagram
    raw = dict(reviewer='Test', evidence='Synthetic drawing', zones=[dict(name='Z1', shape='polygon', reach=None, angle=None, points=points)])
    if valid:
        assert clean_diagram(raw)['zones'][0]['points'] == points
    else:
        with pytest.raises(ValueError, match='Polygon'):
            clean_diagram(raw)
