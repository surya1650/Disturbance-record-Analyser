"""Synthetic-only immutable source import, isolation and activation contracts."""
import copy
import hashlib
import io
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

pytest.importorskip('fastapi')

from dranalyser.registry.catalogue import FIELDS, SCHEMA, digest
from dranalyser.registry.catalogue_io import import_snapshot
from dranalyser.registry.catalogue_store import (
    ActivationConflict,
    activate_import,
    active_envelope,
    import_preview,
    list_imports,
    original_import,
    save_import,
)
from tests import test_application as fixtures
from tests.test_source_catalogue import snapshot as legacy_snapshot

openpyxl = pytest.importorskip('openpyxl')
environment = fixtures.environment


def workbook(feeder='Beta'):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = 'SYNTHETIC TL'
    sheet.append(list(FIELDS.values()))
    sheet.append(['Alpha', feeder, None, 42, '03/04/24', 'SYNTHETIC/REF', 220, 20,
                  '2 +j 8', '6 +j 24', '800 /1 A', '220000 /110 V', 'Example/TEST'])
    content = io.BytesIO()
    book.save(content)
    book.close()
    return content.getvalue()


def stored(root, value=b'synthetic original', **source_extra):
    source = {'kind': 'xlsx', 'sha256': hashlib.sha256(value).hexdigest(),
              'file_name': 'synthetic.xlsx', **source_extra}
    snapshot = {'schema': 'dranalyser.xlsx-snapshot.v1', 'source': source, 'sheets': []}
    catalogue = {'schema': SCHEMA, 'source': source, 'snapshot_hash': digest(snapshot),
                 'rows': [], 'summary': {'rows': 0}, 'limits': 'Unreviewed source evidence.'}
    return save_import(root, value, snapshot, {'catalogue_hash': digest(catalogue), 'catalogue': catalogue})


def upload(client, raw=None, filename='synthetic.xlsx'):
    return client.post('/api/catalogue/imports', files={'file': (filename, raw or workbook(),
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})


def test_legacy_fallback_is_read_only(tmp_path):
    assert active_envelope(tmp_path) is None
    snapshot = tmp_path / 'legacy-snapshot.json'
    snapshot.write_text(json.dumps(legacy_snapshot()))
    legacy = tmp_path / 'source-catalogue.json'
    envelope = import_snapshot(snapshot, legacy)
    before = legacy.read_bytes()
    assert active_envelope(tmp_path) == envelope
    assert list_imports(tmp_path) == {'items': [], 'active_hash': envelope['catalogue_hash']}
    assert not (tmp_path / 'catalogue-index.db').exists()
    assert legacy.read_bytes() == before


def test_immutable_duplicate_preserves_first_metadata_and_original(tmp_path):
    first = stored(tmp_path, retrieved_at='first')
    duplicate = stored(tmp_path, retrieved_at='second')
    assert duplicate == first
    assert original_import(tmp_path, first['import_id']).read_bytes() == b'synthetic original'
    assert active_envelope(tmp_path) is None
    assert len(list_imports(tmp_path)['items']) == 1
    assert not list((tmp_path / 'catalogue-imports').glob('.staging-*'))


def test_concurrent_activation_cas_has_one_winner_and_keeps_versions(tmp_path):
    first, second = stored(tmp_path, b'first'), stored(tmp_path, b'second')

    def activate(item):
        try:
            return activate_import(tmp_path, item['import_id'], None)
        except ActivationConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(activate, [first, second]))
    assert sum(result is not None for result in results) == 1
    winner = next(result for result in results if result)
    loser = first if winner['import_id'] == second['import_id'] else second
    assert active_envelope(tmp_path)['catalogue_hash'] == winner['catalogue_hash']
    activate_import(tmp_path, loser['import_id'], winner['catalogue_hash'])
    assert active_envelope(tmp_path)['catalogue_hash'] == loser['catalogue_hash']
    assert import_preview(tmp_path, winner['import_id'])['catalogue_hash'] == winner['catalogue_hash']
    with sqlite3.connect(tmp_path / 'catalogue-index.db') as connection:
        history = connection.execute('SELECT previous_hash, catalogue_hash FROM activations ORDER BY sequence').fetchall()
    assert history == [(None, winner['catalogue_hash']), (winner['catalogue_hash'], loser['catalogue_hash'])]


@pytest.mark.parametrize('filename', ['original.xlsx', 'snapshot.json', 'catalogue.json', 'manifest.json'])
def test_altered_or_incomplete_import_is_never_activated_or_downloaded(tmp_path, filename):
    item = stored(tmp_path)
    path = tmp_path / 'catalogue-imports' / item['import_id'] / filename
    if filename == 'original.xlsx':
        path.write_bytes(b'altered')
    else:
        document = json.loads(path.read_text())
        (document['catalogue'] if filename == 'catalogue.json' else document)['schema'] = 'altered'
        path.write_text(json.dumps(document))
    for action in (lambda: import_preview(tmp_path, item['import_id']),
                   lambda: activate_import(tmp_path, item['import_id'], None),
                   lambda: original_import(tmp_path, item['import_id'])):
        with pytest.raises(ValueError):
            action()
    assert active_envelope(tmp_path) is None


def test_mismatched_original_hash_and_nonfinite_metadata_are_refused(tmp_path):
    item = stored(tmp_path)
    directory = tmp_path / 'catalogue-imports' / item['import_id']
    snapshot = json.loads((directory / 'snapshot.json').read_text())
    catalogue = json.loads((directory / 'catalogue.json').read_text())['catalogue']
    with pytest.raises(ValueError, match='checksum'):
        save_import(tmp_path, b'other original', snapshot, {'catalogue_hash': digest(catalogue), 'catalogue': catalogue})
    bad = copy.deepcopy(snapshot)
    bad['source']['untrusted'] = float('nan')
    with pytest.raises(ValueError):
        save_import(tmp_path, b'synthetic original', bad, {'catalogue_hash': digest(catalogue), 'catalogue': catalogue})
    manifest = directory / 'manifest.json'
    manifest.write_text(manifest.read_text().replace('"created_at":', '"invalid": NaN, "created_at":'))
    with pytest.raises(ValueError, match='Non-finite'):
        import_preview(tmp_path, item['import_id'])


def test_failed_staging_leaves_no_partial_import(tmp_path, monkeypatch):
    from dranalyser.registry import catalogue_store
    original_write = catalogue_store._write

    def interrupted(path, value):
        if path.name == 'catalogue.json':
            raise OSError('synthetic disk failure')
        return original_write(path, value)

    monkeypatch.setattr(catalogue_store, '_write', interrupted)
    with pytest.raises(OSError, match='synthetic disk failure'):
        stored(tmp_path)
    assert list((tmp_path / 'catalogue-imports').iterdir()) == []
    assert active_envelope(tmp_path) is None


def test_history_is_bounded_but_all_versions_remain(tmp_path):
    items = [stored(tmp_path, f'synthetic {index}'.encode()) for index in range(22)]
    assert len(list_imports(tmp_path)['items']) == 20
    assert len(list((tmp_path / 'catalogue-imports').iterdir())) == 22
    assert import_preview(tmp_path, items[0]['import_id'])['catalogue_hash'] == items[0]['catalogue_hash']


def test_api_preview_activation_download_and_registry_isolation(environment):
    client, app, _, registry = environment
    root = app.state.store.root
    snapshot = root / 'legacy-snapshot.json'
    snapshot.write_text(json.dumps(legacy_snapshot()))
    legacy = root / 'source-catalogue.json'
    old = import_snapshot(snapshot, legacy)
    legacy_bytes = legacy.read_bytes()
    registry_before = {path.name: path.read_bytes() for path in registry.iterdir()}
    raw = workbook()
    response = upload(client, raw)
    assert response.status_code == 200, response.text
    item = response.json()
    identity = item['import_id']
    assert identity == hashlib.sha256(raw).hexdigest() == item['source']['sha256']
    assert item['summary']['rows'] == 1 and not item['active']
    assert item['expected_active_hash'] == old['catalogue_hash']
    assert client.get('/api/catalogue').json()['catalogue_hash'] == old['catalogue_hash']
    assert upload(client, raw, 'renamed.xlsx').json() == item
    detail = client.get('/api/catalogue/imports/'+identity).json()
    assert detail['catalogue']['rows'][0]['station'] == 'Alpha'
    assert not detail['catalogue']['rows'][0]['field_verified']
    original = client.get('/api/catalogue/imports/'+identity+'/original')
    assert original.content == raw
    assert 'original.xlsx' in original.headers['content-disposition']
    activated = client.post('/api/catalogue/imports/'+identity+'/activate',
                            json={'expected_active_hash': old['catalogue_hash']})
    assert activated.status_code == 200 and activated.json()['active']
    assert client.get('/api/catalogue').json()['catalogue_hash'] == item['catalogue_hash']
    assert client.get('/api/catalogue/imports').json()['items'][0]['active']
    stale = client.post('/api/catalogue/imports/'+identity+'/activate',
                        json={'expected_active_hash': old['catalogue_hash']})
    assert stale.status_code == 409
    assert legacy.read_bytes() == legacy_bytes
    assert registry_before == {path.name: path.read_bytes() for path in registry.iterdir()}
    assert not app.state.store.list()


def test_api_auth_validation_size_and_missing_imports(environment, monkeypatch):
    client, app, _, _ = environment
    token = client.headers.pop('X-DR-Token')
    assert upload(client).status_code == 401
    client.headers['X-DR-Token'] = token
    assert client.post('/api/catalogue/imports', headers={'Origin': 'https://example.invalid'},
                       files={'file': ('synthetic.xlsx', workbook())}).status_code == 403
    for raw, filename in [(b'not a workbook', 'synthetic.xlsx'), (workbook(), 'unsafe.xlsm')]:
        assert upload(client, raw, filename).status_code == 400
    from dranalyser.application import catalogue_import
    monkeypatch.setattr(catalogue_import, 'MAX_WORKBOOK_BYTES', 1024)
    assert upload(client, b'x' * 1025).status_code == 413
    assert client.get('/api/catalogue/imports/missing').status_code == 404
    assert client.get('/api/catalogue/imports/missing/original').status_code == 404
    assert client.post('/api/catalogue/imports/missing/activate', json={}).status_code == 422
    assert client.post('/api/catalogue/imports/missing/activate',
                       json={'expected_active_hash': None}).status_code == 404
    assert not list((app.state.store.root / 'catalogue-imports').glob('*'))
