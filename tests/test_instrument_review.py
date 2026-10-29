"""Missing instrument-rating questions require evidence and preserve original bytes."""
import hashlib
import json

import numpy as np
import pytest

from dranalyser.application.worker import Worker
from dranalyser.comtrade.parser import read_cff, read_comtrade
from dranalyser.workbench.source_inspection import _source
from dranalyser.workbench.ratio_inputs import prepare_ratio_copy, required_ratios
from tests.test_application import environment as environment, payload


def upload_missing_ratios(environment, cff=False, kilo=False):
    client, app, source, registry = environment
    cfg = source/'S/event.cfg'
    lines = cfg.read_text().splitlines()
    na = int(lines[1].split(',')[1][:-1])
    for i in range(2, 2+na):
        fields = lines[i].split(',')
        factor = 1000 if fields[4] == 'A' else 2000
        fields[5] = str(float(fields[5])/factor)
        if kilo:
            fields[5] = str(float(fields[5])/1000)
            fields[4] = 'K'+fields[4]
        fields[10:13] = ['1', '0', 'S']
        lines[i] = ','.join(fields)
    cfg.write_text('\n'.join(lines)+'\n')
    if cff:
        raw = b'--- file type: CFG ---\n'+cfg.read_bytes()+b'--- file type: DAT ASCII ---\n'+cfg.with_suffix('.dat').read_bytes()
        files = [('files', ('event.cff', raw))]
        filename = 'event.cff'
    else:
        files, filename = payload(source), 'S/event.cfg'
    response = client.post('/api/intake', files=files, data={'name': 'Synthetic missing instrument ratings'})
    assert response.status_code == 202, response.text
    identity = response.json()['incident_id']
    assert Worker(app.state.store, registry).once()
    row = app.state.store.get(identity)
    decoded, item = _source(app.state.store.root, row, filename)
    assert item['blocked'] and required_ratios(decoded)
    review = dict(record_hash=item['content_hash'], reviewer='Synthetic test engineer',
        evidence='Known transformer ratings used by the independent synthetic generator.', confirmed_secondary=True,
        ratios={h['id']: dict(primary=1000, secondary=1) if h['declared_units'].endswith('A') else dict(primary=220000, secondary=110)
                for h in required_ratios(decoded)})
    return client, app, registry, identity, row, filename, review


@pytest.mark.parametrize(('cff', 'kilo'), [(False, False), (True, False), (False, True), (True, True)])
def test_preview_and_save_traceable_reviewed_copy_then_analyse(environment, cff, kilo):
    oracle = read_comtrade(str(environment[2]/'S/event.cfg'))
    client, app, registry, identity, before, filename, review = upload_missing_ratios(environment, cff, kilo)
    url = f'/api/incidents/{identity}/instrument-review'
    request = dict(record=filename, revision=1, review=review)
    response = client.post(url, json=request)
    assert response.status_code == 200, response.text
    assert response.json()['blocked'] is False, response.json()
    assert app.state.store.get(identity)['number'] == 1
    assert app.state.store.get(identity)['files'] == before['files']
    response = client.post(url, json={**request, 'save': True})
    assert response.status_code == 200, response.text
    new_name = response.json()['reviewed_record']
    assert response.json()['revision'] == 2
    assert Worker(app.state.store, registry).once()
    after = app.state.store.get(identity)
    assert after['number'] == 2 and after['state'] == 'needs_review'
    reviewed = next(f for f in after['bundle']['files'] if f['name'] == new_name)
    assert not reviewed['blocked']
    folder = after['bundle']['root']
    from pathlib import Path
    folder = Path(folder)
    restored = read_cff(str(folder/new_name)) if cff else read_comtrade(str(folder/new_name))
    for channel in oracle.analog:
        np.testing.assert_allclose(restored.analog[channel], oracle.analog[channel], rtol=1e-12, atol=1e-8)
    manifest = json.loads((folder/new_name).parent.joinpath('instrument-review.json').read_text())
    assert manifest['original_files_unchanged'] and not manifest['samples_changed']
    assert manifest['review'] == review
    if not cff:
        old_dat = next(f['sha256'] for f in before['files'] if f['name'].endswith('.dat'))
        assert hashlib.sha256((folder/new_name).with_suffix('.dat').read_bytes()).hexdigest() == old_dat
    else:
        from dranalyser.comtrade.source_container import _framed
        original = (folder/filename).read_bytes()
        derived = (folder/new_name).read_bytes()
        assert original[_framed(original)[1].end():] == derived[_framed(derived)[1].end():]
    assert app.state.store.get(identity, 1)['files'] == before['files']
    result = client.post(f'/api/incidents/{identity}/review', json={'revision': 2, 'line_id': 'SYNTHETIC-DEMO',
        'assignments': {filename: {'end': '', 'role': 'excluded'}, new_name: {'end': 'S', 'role': 'primary'}}})
    assert result.status_code == 202, result.text
    assert Worker(app.state.store, registry).once()
    complete = app.state.store.get(identity)
    assert complete['state'] == 'completed', complete.get('error')
    assert complete['result']['used']['S'] == new_name


@pytest.mark.parametrize('problem', ['hash', 'zero', 'negative', 'reviewer', 'evidence', 'confirmation', 'missing_channel', 'extra_field'])
def test_missing_or_unverified_inputs_never_create_a_copy(environment, problem):
    client, app, _, identity, before, filename, review = upload_missing_ratios(environment)
    if problem == 'hash':
        review['record_hash'] = '0'*64
    elif problem in ('zero', 'negative'):
        review['ratios']['A1']['secondary'] = 0 if problem == 'zero' else -1
    elif problem in ('reviewer', 'evidence'):
        review[problem] = ''
    elif problem == 'confirmation':
        review['confirmed_secondary'] = False
    elif problem == 'missing_channel':
        del review['ratios']['A1']
    else:
        review['automatic_ratio_default'] = 800
    response = client.post(f'/api/incidents/{identity}/instrument-review', json={
        'record': filename, 'revision': 1, 'review': review, 'save': True})
    assert response.status_code == 400, response.text
    assert app.state.store.get(identity)['number'] == 1
    assert app.state.store.get(identity)['files'] == before['files']


def test_rating_review_does_not_clear_independent_timing_block(environment):
    client, app, _, _, row, filename, review = upload_missing_ratios(environment)
    from pathlib import Path
    folder = Path(row['bundle']['root'])
    dat = folder/'S/event.dat'
    lines = dat.read_text().splitlines()
    fields = lines[30].split(',')
    fields[1] = '0'
    lines[30] = ','.join(fields)
    dat.write_text('\n'.join(lines)+'\n')
    cfg_lines=(folder/filename).read_text().splitlines()
    counts=cfg_lines[1].split(',')
    j=2+int(counts[1][:-1])+int(counts[2][:-1])
    cfg_lines[j+1]='0'
    cfg_lines[j+2]='0,370'
    (folder/filename).write_text('\n'.join(cfg_lines)+'\n')
    cfg = (folder/filename).read_bytes()
    content = dat.read_bytes()
    for item in row['files']:
        if item['name'] in ('S/event.dat',filename):
            item['sha256'] = hashlib.sha256(content if item['name'].endswith('.dat') else cfg).hexdigest()
    original = next(f for f in row['bundle']['files'] if f['name'] == filename)
    original['content_hash'] = hashlib.sha256(cfg+content).hexdigest()
    review['record_hash'] = original['content_hash']
    prepared = prepare_ratio_copy(app.state.store.root, row, filename, review)
    assert prepared['blocked']
    assert any('[BLOCK TIME-DAT]' in f for f in prepared['flags'])
    assert not any('[BLOCK RATIO-PS]' in f for f in prepared['flags'])


def test_requirements_and_download_are_source_bound_and_do_not_save(environment):
    import io
    import zipfile
    client, app, _, identity, before, filename, review = upload_missing_ratios(environment)
    base = f'/api/incidents/{identity}/instrument-review'
    response = client.get(base, params={'record': filename, 'revision': 1})
    assert response.status_code == 200, response.text
    required = response.json()
    assert required['record_hash'] == review['record_hash']
    assert {h['id'] for h in required['required_ratios']} == set(review['ratios'])
    assert any('[BLOCK RATIO-PS]' in flag for flag in required['blocking_findings'])
    response = client.post(base+'/export', json={'record': filename, 'revision': 1, 'review': review})
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        cfg = next(name for name in names if name.endswith('/reviewed.cfg'))
        dat = cfg.removesuffix('.cfg')+'.dat'
        original_dat = next(f['sha256'] for f in before['files'] if f['name'].endswith('.dat'))
        assert hashlib.sha256(archive.read(dat)).hexdigest() == original_dat
        manifest = json.loads(archive.read(cfg.rsplit('/', 1)[0]+'/instrument-review.json'))
        assert manifest['review'] == review
        assert manifest['operationally_blocked'] is False
        assert manifest['original_files_unchanged'] and not manifest['samples_changed']
        assert manifest['original_sha256'] == required['source_sha256']
    assert app.state.store.get(identity) == before
    assert client.post(base+'/export', json={'record': filename, 'revision': 1, 'review': review, 'save': True}).status_code == 400
    assert client.get(base, params={'record': '../escape.cfg', 'revision': 1}).status_code == 400


@pytest.mark.parametrize('revision', [True, 0, -1, 2147483648, 1.5])
def test_invalid_revision_never_creates_a_ratio_copy(environment, revision):
    client, app, _, identity, before, filename, review = upload_missing_ratios(environment)
    response = client.post(f'/api/incidents/{identity}/instrument-review', json={
        'record': filename, 'revision': revision, 'review': review, 'save': True})
    assert response.status_code == 400, response.text
    assert app.state.store.get(identity) == before


def test_stale_save_preserves_the_newer_incident_revision(environment):
    client, app, registry, identity, before, filename, review = upload_missing_ratios(environment)
    endpoint = f'/api/incidents/{identity}/instrument-review'
    request = {'record': filename, 'revision': 1, 'review': review, 'save': True}
    first = client.post(endpoint, json=request)
    assert first.status_code == 200, first.text
    Worker(app.state.store, registry).once()
    newer = app.state.store.get(identity)
    altered = json.loads(json.dumps(request))
    altered['review']['evidence'] += ' A second review submitted against an obsolete revision.'
    response = client.post(endpoint, json=altered)
    assert response.status_code == 409, response.text
    assert app.state.store.get(identity) == newer
    assert app.state.store.get(identity, 1) == before


@pytest.mark.parametrize('field,value', [('secondary', True), ('primary', False), ('secondary', 1e-10), ('primary', 1e13)])
def test_invalid_numeric_rating_types_or_ranges_refuse(environment, field, value):
    client, app, _, identity, before, filename, review = upload_missing_ratios(environment)
    review['ratios']['A1'][field] = value
    response = client.post(f'/api/incidents/{identity}/instrument-review', json={
        'record': filename, 'revision': 1, 'review': review, 'save': True})
    assert response.status_code == 400, response.text
    assert app.state.store.get(identity) == before
