"""Source-bound ratings update the same logical capture and preserve its bytes."""
import copy
from pathlib import Path

import numpy as np
import pytest

from dranalyser.application.worker import Worker
from dranalyser.comtrade.conformance import check
from dranalyser.comtrade.parser import read_cff, read_comtrade
from dranalyser.workbench.samples import sample_interval
from dranalyser.workbench.source_inspection import _source
from tests.test_application import environment as environment
from tests.test_instrument_review import upload_missing_ratios


@pytest.mark.parametrize(('cff', 'kilo'), [(False, False), (True, False), (False, True), (True, True)])
def test_same_record_save_keeps_names_bytes_and_normalizes_once(environment, cff, kilo):
    oracle = read_comtrade(str(environment[2]/'S/event.cfg'))
    client, app, registry, identity, before, name, review = upload_missing_ratios(environment, cff, kilo)
    original, _ = _source(app.state.store.root, before, name)
    raw_before = copy.deepcopy(original)
    base = f'/api/incidents/{identity}/instrument-review'
    response = client.post(base, json=dict(record=name, revision=1, review=review, save=True))
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['record'] == saved['reviewed_record'] == name
    assert saved['save_mode'] == 'same-record' and saved['revision'] == 2
    assert Worker(app.state.store, registry).once()
    after = app.state.store.get(identity)
    assert after['files'] == before['files']
    assert [f['name'] for f in after['bundle']['files'] if f['kind'] == 'comtrade'] == [name]
    assert app.state.store.get(identity, 1) == before
    source, item = _source(app.state.store.root, after, name)
    assert not item['blocked'] and source['instrument_review'] == review
    assert source['source_sha256'] == original['source_sha256']
    assert original == raw_before
    assert source['recorded_header_inventory'] == original['header_inventory']
    for channel in source['channels']:
        if channel['key'] in review['ratios']:
            np.testing.assert_allclose(channel['values'], oracle.analog[channel['label']], rtol=1e-12, atol=1e-8)
            assert 'reviewed ratings' in channel['units']
        else:
            assert channel['units'] == 'raw counts'
            assert channel['values'] == next(c['values'] for c in original['channels'] if c['key'] == channel['key'])
    path = Path(after['bundle']['root'])/name
    record = read_cff(str(path), instrument_review=review) if cff else read_comtrade(str(path), instrument_review=review)
    check(record)
    assert not record.blocked()
    assert record.content_hash == item['content_hash']
    for channel in ('IA', 'IB', 'IC', 'VA', 'VB', 'VC'):
        np.testing.assert_allclose(record.analog[channel], oracle.analog[channel], rtol=1e-12, atol=1e-8)
    current = client.get(base, params=dict(record=name, revision=2)).json()
    assert not current['required_ratios']
    assert {h['id'] for h in current['reviewable_ratios']} == set(review['ratios'])
    assert current['applied_review'] == review
    same = client.post(base, json=dict(record=name, revision=2, review=review, save=True))
    assert same.status_code == 200 and same.json()['revision'] == 2 and same.json()['duplicate']


def test_review_survives_end_assignment_and_native_operational_replay(environment):
    oracle = read_comtrade(str(environment[2]/'S/event.cfg'))
    client, app, registry, identity, before, name, review = upload_missing_ratios(environment)
    response = client.post(f'/api/incidents/{identity}/instrument-review',
        json=dict(record=name, revision=1, review=review, save=True))
    assert response.status_code == 200, response.text
    Worker(app.state.store, registry).once()
    # End/line selection does not resend (or silently discard) capture-bound ratings.
    response = client.post(f'/api/incidents/{identity}/review', json=dict(revision=2,
        line_id='SYNTHETIC-DEMO', assignments={name: dict(end='S', role='primary')}))
    assert response.status_code == 202, response.text
    assert Worker(app.state.store, registry).once()
    after = app.state.store.get(identity)
    assert after['state'] == 'completed', after.get('error')
    assert after['metadata']['assignments'][name]['instrument_review'] == review
    assert after['result']['used'] == {'S': name}
    measured = sample_interval(app.state.store.root, after, name, 'IA', .1, .15)
    for index, _, value in measured['samples']:
        assert value == pytest.approx(oracle.analog['IA'][index])
    assert not any('RATIO-PS' in f for f in after['bundle']['files'][0]['flags'])
    assert after['files'] == before['files']


def test_editing_saved_answers_uses_original_samples_and_does_not_reuse_old_cache(environment):
    from dranalyser.workbench.source_diagnostics import diagnose_source
    from dranalyser.workbench.source_models import SourceModelCache
    client, app, registry, identity, before, name, review = upload_missing_ratios(environment)
    url = f'/api/incidents/{identity}/instrument-review'
    assert client.post(url, json=dict(record=name, revision=1, review=review, save=True)).status_code == 200
    Worker(app.state.store, registry).once()
    row = app.state.store.get(identity)
    first, _ = _source(app.state.store.root, row, name)
    first_values = copy.deepcopy(first['channels'])
    model_cache = SourceModelCache()
    first_models = diagnose_source(app.state.store.root, row, name, model_cache=model_cache)
    changed = copy.deepcopy(review)
    for values in changed['ratios'].values():
        values['primary'] *= 2
    # Same source path/hash with different review must have a distinct decode/cache key.
    transient = copy.deepcopy(row)
    transient['metadata']['assignments'][name]['instrument_review'] = changed
    second, _ = _source(app.state.store.root, transient, name)
    for a, b in zip(first['channels'], second['channels'], strict=True):
        factor = 2 if a['key'] in review['ratios'] else 1
        np.testing.assert_allclose(b['values'], np.asarray(a['values'])*factor)
    second_models = diagnose_source(app.state.store.root, transient, name, model_cache=model_cache)
    assert second_models['job_id'] != first_models['job_id']
    assert second_models['instrument_review_sha256'] != first_models['instrument_review_sha256']
    for a, b in zip(first_models['channels'], second_models['channels'], strict=True):
        factor = 2 if a['key'] in review['ratios'] else 1
        assert b['sample_max'] == pytest.approx(a['sample_max']*factor)
    assert first['channels'] == first_values
    response = client.post(url, json=dict(record=name, revision=2, review=changed, save=True))
    assert response.status_code == 200, response.text
    assert response.json()['revision'] == 3
    Worker(app.state.store, registry).once()
    latest = app.state.store.get(identity)
    assert latest['files'] == before['files']
    assert app.state.store.get(identity, 2) == row
    assert _source(app.state.store.root, latest, name)[0]['channels'] == second['channels']


def test_replayed_intake_assignments_keep_saved_ratings(environment):
    import json
    from tests.test_application import payload
    client, app, registry, identity, _, name, review = upload_missing_ratios(environment)
    assert client.post(f'/api/incidents/{identity}/instrument-review',
        json=dict(record=name, revision=1, review=review, save=True)).status_code == 200
    assert Worker(app.state.store, registry).once()
    prior = app.state.store.get(identity)
    response = client.post('/api/intake', files=payload(environment[2]), data=dict(
        incident_id=identity, expected_revision='2', metadata=json.dumps(dict(
            line_id='SYNTHETIC-DEMO', auto_analyse=True,
            assignments={name: dict(end='S', role='primary')}))))
    assert response.status_code == 202, response.text
    assert Worker(app.state.store, registry).once()
    after = app.state.store.get(identity)
    assert after['state'] == 'completed', after.get('error')
    assert after['metadata']['assignments'][name]['instrument_review'] == review
    assert app.state.store.get(identity, 2) == prior


def test_changing_ratings_keeps_old_report_and_withholds_prior_rx_scaling_confirmation(environment):
    import json
    from tests.test_rx_review import inputs
    from tests.test_settings import RIO_FIXTURE
    client, app, registry, identity, _, name, review = upload_missing_ratios(environment)
    endpoint = f'/api/incidents/{identity}/instrument-review'
    assert client.post(endpoint, json=dict(record=name, revision=1, review=review, save=True)).status_code == 200
    assert Worker(app.state.store, registry).once()
    record = app.state.store.get(identity)['bundle']['files'][0]
    from hashlib import sha256
    rx = dict(inputs()[3], record_hash=record['content_hash'], settings_hash=sha256(RIO_FIXTURE.encode()).hexdigest(),
              instrument_review_sha256=record['instrument_review_sha256'])
    response = client.post('/api/intake', files=[('files', ('S/event.rio', RIO_FIXTURE.encode()))], data=dict(
        incident_id=identity, expected_revision='2', metadata=json.dumps(dict(
            line_id='SYNTHETIC-DEMO', auto_analyse=True,
            assignments={name: dict(end='S', role='primary', rx_review=rx)}))))
    assert response.status_code == 202, response.text
    assert Worker(app.state.store, registry).once()
    before = app.state.store.get(identity)
    assert before['state'] == 'completed', before.get('error')
    old_nav = client.get(f'/api/incidents/{identity}/navigator?revision=3').content
    old_report = client.get(f'/api/incidents/{identity}/report?revision=3').content
    assert json.loads(old_nav)['records'][0]['rx']['zones']['phase']
    changed = copy.deepcopy(review)
    changed['ratios']['A1']['primary'] *= 2
    response = client.post(endpoint, json=dict(record=name, revision=3, review=changed, save=True))
    assert response.status_code == 200, response.text
    assert Worker(app.state.store, registry).once()
    nav = client.get(f'/api/incidents/{identity}/navigator?revision=4').json()['records'][0]['rx']
    assert not nav['zones']['phase'] and 'AG' not in nav['loops']
    assert any('stale' in reason for reason in nav['context']['ground_missing'])
    assert app.state.store.get(identity, 3) == before
    assert client.get(f'/api/incidents/{identity}/navigator?revision=3').content == old_nav
    assert client.get(f'/api/incidents/{identity}/report?revision=3').content == old_report


def test_primary_channels_keep_their_original_scale_while_secondary_channel_is_reviewed(environment):
    from dranalyser.comtrade.source_observations import load_source
    path = environment[2]/'S/event.cfg'
    oracle = read_comtrade(str(path))
    lines = path.read_text().splitlines()
    fields = lines[2].split(',')
    fields[5] = str(float(fields[5])/1000)
    fields[10:13] = ['1', '0', 'S']
    lines[2] = ','.join(fields)
    path.write_text('\n'.join(lines)+'\n')
    original = read_comtrade(str(path))
    review = dict(record_hash=original.content_hash, reviewer='Synthetic test engineer',
        evidence='Independent synthetic transformer declaration.', confirmed_secondary=True,
        ratios={'A1': dict(primary=1000, secondary=1)})
    effective = read_comtrade(str(path), instrument_review=review)
    observed = load_source(path, instrument_review=review)
    for channel in ('IA', 'IB', 'IC', 'VA', 'VB', 'VC'):
        np.testing.assert_allclose(effective.analog[channel], oracle.analog[channel])
        data = next(c for c in observed['channels'] if c['label'] == channel)
        np.testing.assert_allclose(data['values'], oracle.analog[channel])
    forged = copy.deepcopy(review)
    forged['ratios']['A2'] = dict(primary=2000, secondary=1)
    with pytest.raises(ValueError, match='original missing secondary-ratio'):
        read_comtrade(str(path), instrument_review=forged)


def test_container_review_requires_original_outer_hash(environment):
    import hashlib
    from dranalyser.comtrade.source_container import _framed
    client, app, registry, identity, row, name, review = upload_missing_ratios(environment, cff=True)
    raw = (Path(row['bundle']['root'])/name).read_bytes()
    cfg, marker = _framed(raw)
    forged = copy.deepcopy(review)
    forged['record_hash'] = hashlib.sha256(cfg+raw[marker.end():]).hexdigest()
    assert forged['record_hash'] != review['record_hash']
    response = client.post(f'/api/incidents/{identity}/instrument-review',
        json=dict(record=name, revision=1, review=forged, save=True))
    assert response.status_code == 400, response.text
    with pytest.raises(ValueError, match='different original recording'):
        read_cff(str(Path(row['bundle']['root'])/name), instrument_review=forged)
    assert app.state.store.get(identity) == row


def test_partial_answers_preserve_remaining_named_phase_block(environment):
    client, app, registry, identity, before, name, review = upload_missing_ratios(environment)
    missing = next(iter(review['ratios']))
    del review['ratios'][missing]
    url = f'/api/incidents/{identity}/instrument-review'
    response = client.post(url, json=dict(record=name, revision=1, review=review, save=True))
    assert response.status_code == 200, response.text
    assert response.json()['blocked']
    assert any('[BLOCK RATIO-PS]' in flag for flag in response.json()['flags'])
    Worker(app.state.store, registry).once()
    current = client.get(url, params=dict(record=name, revision=2)).json()
    assert {h['id'] for h in current['required_ratios']} == {missing}
    assert current['applied_review'] == review
    assert app.state.store.get(identity)['files'] == before['files']


def test_missing_unused_auxiliary_ratios_do_not_force_extra_phase_inputs(environment):
    # Add an independently recorded, unmapped secondary auxiliary channel.
    client, app, source, registry = environment
    cfg = source/'S/event.cfg'
    lines = cfg.read_text().splitlines()
    total, analog, digital = lines[1].split(',')
    n = int(analog[:-1])
    lines[1] = f'{int(total)+1},{n+1}A,{digital}'
    lines.insert(2+n, f'{n+1},Auxiliary sensor,,,A,.01,0,0,-32767,32767,1,0,S')
    cfg.write_text('\n'.join(lines)+'\n')
    dat = source/'S/event.dat'
    data = []
    for line in dat.read_text().splitlines():
        cells = line.split(',')
        cells.insert(2+n, '17')
        data.append(','.join(cells))
    dat.write_text('\n'.join(data)+'\n')
    # The shared fixture transforms all analogs to missing secondary metadata.
    client, app, registry, identity, _, name, review = upload_missing_ratios(environment)
    assert 'A'+str(n+1) not in review['ratios']
    response = client.post(f'/api/incidents/{identity}/instrument-review',
        json=dict(record=name, revision=1, review=review, save=True))
    assert response.status_code == 200 and not response.json()['blocked'], response.text
    Worker(app.state.store, registry).once()
    source, _ = _source(app.state.store.root, app.state.store.get(identity), name)
    assert source['channels'][-1]['units'] == 'raw counts'
    assert set(source['channels'][-1]['values']) == {17}
