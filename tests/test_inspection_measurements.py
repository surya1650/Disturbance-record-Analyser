"""The cursor measurement route stays source-bound and independent of conformance."""
import copy
import hashlib
import json
import math

import pytest

from dranalyser.application.worker import Worker
from dranalyser.workbench.source_inspection import inspection_measurements, inspection_record, inspection_samples
from tests.test_application import environment as environment
from tests.test_source_inspection import revision as revision


def test_dense_rms_and_cursor_fourier_survive_operational_refusal(revision):
    root, row, folder = revision
    cfg = folder/'event.cfg'
    cfg.write_text(cfg.read_text().replace('0,4\n', '0,121\n'))
    cfg.with_suffix('.dat').write_text(''.join(
        f'{i+1},{i*1000},{10*math.cos(2*math.pi*50*i/1000):.12f},20,0\n'
        for i in range(121)))
    for entry in row['files']:
        entry['sha256'] = hashlib.sha256((folder/entry['name']).read_bytes()).hexdigest()
    before = copy.deepcopy(row)
    metadata = inspection_record(root, row, 'event.cfg')
    assert metadata['nominal_frequency_hz'] == 50
    analog = metadata['channels'][0]
    assert analog['rms_window_s'] == .02
    assert all(p[2] is None for p in analog['rms_trace'][:20])
    assert analog['rms_trace'][80][2] == pytest.approx(math.sqrt(201), rel=1e-9)
    measured = inspection_measurements(root, row, 'event.cfg', ['A1', 'A2'], 80)
    assert measured['window']['stop_index'] == 81
    assert measured['window']['reference_s'] == .08
    assert measured['channels']['A1']['fundamental_rms'] == pytest.approx(20/math.sqrt(2))
    assert measured['channels']['A1']['total_rms'] == pytest.approx(math.sqrt(201))
    assert measured['scaling_verified'] is measured['authorizes_location'] is False
    assert measured['source_sha256'] == metadata['source_sha256']
    native = inspection_samples(root, row, 'event.cfg', 'A1', 80, 85, include_rms=True)
    assert [p[0] for p in native['rms_samples']] == list(range(80, 85))
    assert [p[2] for p in native['rms_samples']] == pytest.approx([math.sqrt(201)]*5)
    assert 'rms_samples' not in inspection_samples(root, row, 'event.cfg', 'D1', 80, 85, include_rms=True)
    assert row == before
    json.dumps(measured, allow_nan=False)


def test_measurement_api_explains_short_support_and_refuses_foreign_choices(environment, revision):
    client, app, _, registry = environment
    _, _, folder = revision
    identity = client.post('/api/intake', files=[('files', (p.name, p.read_bytes()))
                                                for p in folder.iterdir()]).json()['incident_id']
    Worker(app.state.store, registry).once()
    before = client.get(f'/api/incidents/{identity}').json()
    url = f'/api/incidents/{identity}/inspection/measurements'
    query = dict(revision=1, record='event.cfg', channel_ids='["A1"]', index=3)
    response = client.get(url, params=query)
    assert response.status_code == 200, response.text
    out = response.json()
    assert out['channels']['A1']['status'] == 'unavailable'
    assert 'complete trailing' in out['channels']['A1']['reason']
    assert out['channels']['A1']['phasor'] is None
    assert out['authorizes_location'] is False
    for field, value in [('channel_ids', '["D1"]'), ('channel_ids', '["A1","A1"]'),
                         ('channel_ids', '[{}]'), ('channel_ids', '['), ('index', -1),
                         ('index', 4), ('record', '../event.cfg')]:
        refused = client.get(url, params={**query, field: value})
        assert refused.status_code == 400, refused.text
    assert client.get(url, params={**query, 'revision': 999}).status_code == 404
    assert client.get(f'/api/incidents/{identity}').json() == before
