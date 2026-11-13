"""Immutable workbook imports and a separate, transactional source-view pointer.

Activating evidence never approves engineering values or writes the line registry.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone

from .catalogue import SCHEMA, digest
from .catalogue_io import read_catalogue

IMPORT_SCHEMA = 'dranalyser.catalogue-import.v1'
SNAPSHOT_SCHEMA = 'dranalyser.xlsx-snapshot.v1'
HASH = re.compile(r'[0-9a-f]{64}')


class ActivationConflict(ValueError):
    """The caller reviewed an older active source catalogue."""


def _json(path):
    def invalid(value):
        raise ValueError('Non-finite JSON metadata: '+value)
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=invalid)


def _directory(root, import_id):
    if not isinstance(import_id, str) or not HASH.fullmatch(import_id):
        raise KeyError(import_id)
    return Path(root) / 'catalogue-imports' / import_id


def _validate(root, import_id):
    directory = _directory(root, import_id)
    if not directory.is_dir():
        raise KeyError(import_id)
    try:
        return _read_import(directory, import_id)
    except (OSError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Catalogue import is incomplete or has invalid evidence metadata.') from exc


def _read_import(directory, import_id):
    manifest = _json(directory / 'manifest.json')
    snapshot = _json(directory / 'snapshot.json')
    envelope = read_catalogue(directory / 'catalogue.json')
    original_hash = hashlib.sha256((directory / 'original.xlsx').read_bytes()).hexdigest()
    if (manifest.get('schema') != IMPORT_SCHEMA or manifest.get('import_id') != import_id
            or original_hash != import_id or snapshot.get('schema') != SNAPSHOT_SCHEMA
            or snapshot.get('source', {}).get('sha256') != import_id
            or envelope['catalogue'].get('source') != snapshot.get('source')
            or manifest.get('snapshot_hash') != digest(snapshot)
            or envelope['catalogue'].get('snapshot_hash') != digest(snapshot)
            or manifest.get('catalogue_hash') != envelope['catalogue_hash']):
        raise ValueError('Catalogue import checksum/schema mismatch; immutable evidence was altered.')
    return manifest, envelope


@contextmanager
def _connection(root, *, write=False):
    path = Path(root) / 'catalogue-index.db'
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=30)
    else:
        connection = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=30)
    try:
        if write:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS imports (
                    import_id TEXT PRIMARY KEY, catalogue_hash TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS active (singleton INTEGER PRIMARY KEY CHECK(singleton=1), import_id TEXT);
                CREATE TABLE IF NOT EXISTS activations (
                    sequence INTEGER PRIMARY KEY, import_id TEXT NOT NULL,
                    previous_hash TEXT, catalogue_hash TEXT NOT NULL, activated_at TEXT NOT NULL);
            ''')
        with connection:
            yield connection
    finally:
        connection.close()


def _active(root, connection=None):
    if connection is not None:
        row = connection.execute('SELECT import_id FROM active WHERE singleton=1').fetchone()
        if row and row[0]:
            return _indexed(root, connection, row[0])[1]
    legacy = Path(root) / 'source-catalogue.json'
    return read_catalogue(legacy) if legacy.is_file() else None


def _indexed(root, connection, import_id):
    row = connection.execute('SELECT catalogue_hash FROM imports WHERE import_id=?', (import_id,)).fetchone()
    if row is None:
        raise KeyError(import_id)
    result = _validate(root, import_id)
    if row[0] != result[1]['catalogue_hash']:
        raise ValueError('Catalogue index checksum mismatch.')
    return result


def active_envelope(root):
    """Read active evidence, or the checksum-validated legacy file without migrating it."""
    if not (Path(root) / 'catalogue-index.db').is_file():
        return _active(root)
    with _connection(root) as connection:
        return _active(root, connection)


def _metadata(manifest, envelope, active):
    catalogue = envelope['catalogue']
    active_hash = active['catalogue_hash'] if active else None
    return {'import_id': manifest['import_id'], 'catalogue_hash': envelope['catalogue_hash'],
            'source': catalogue['source'], 'summary': catalogue['summary'], 'limits': catalogue['limits'],
            'created_at': manifest['created_at'], 'expected_active_hash': active_hash,
            'active': active_hash == envelope['catalogue_hash']}


def import_preview(root, import_id):
    if not (Path(root) / 'catalogue-index.db').is_file():
        raise KeyError(import_id)
    with _connection(root) as connection:
        manifest, envelope = _indexed(root, connection, import_id)
        return {**_metadata(manifest, envelope, _active(root, connection)), 'catalogue': envelope['catalogue']}


def list_imports(root):
    if not (Path(root) / 'catalogue-index.db').is_file():
        active = active_envelope(root)
        return {'items': [], 'active_hash': active['catalogue_hash'] if active else None}
    with _connection(root) as connection:
        active = _active(root, connection)
        rows = connection.execute('SELECT import_id FROM imports ORDER BY created_at DESC, rowid DESC LIMIT 20')
        items = [_metadata(*_indexed(root, connection, row[0]), active) for row in rows.fetchall()]
        return {'items': items, 'active_hash': active['catalogue_hash'] if active else None}


def _write(path, value):
    content = value if isinstance(value, bytes) else (json.dumps(
        value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')
    with path.open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def save_import(root, original, snapshot, envelope):
    """Publish a complete immutable directory, then index it; identical bytes retain their first import."""
    import_id = hashlib.sha256(original).hexdigest()
    catalogue = envelope.get('catalogue', {})
    if (snapshot.get('schema') != SNAPSHOT_SCHEMA or catalogue.get('schema') != SCHEMA
            or snapshot.get('source', {}).get('sha256') != import_id
            or catalogue.get('source') != snapshot.get('source')
            or catalogue.get('snapshot_hash') != digest(snapshot)
            or envelope.get('catalogue_hash') != digest(catalogue)):
        raise ValueError('Catalogue import checksum/schema mismatch.')
    manifest = {'schema': IMPORT_SCHEMA, 'import_id': import_id, 'snapshot_hash': digest(snapshot),
                'catalogue_hash': envelope['catalogue_hash'],
                'created_at': datetime.now(timezone.utc).isoformat()}
    destination = _directory(root, import_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.staging-', dir=destination.parent))
    try:
        for filename, content in [('original.xlsx', original), ('snapshot.json', snapshot),
                                  ('catalogue.json', envelope), ('manifest.json', manifest)]:
            _write(stage / filename, content)
        with _connection(root, write=True) as connection:
            connection.execute('BEGIN IMMEDIATE')
            if destination.exists():
                manifest, envelope = _validate(root, import_id)
            else:
                os.rename(stage, destination)
            connection.execute('INSERT OR IGNORE INTO imports VALUES (?, ?, ?)',
                               (import_id, envelope['catalogue_hash'], manifest['created_at']))
            _indexed(root, connection, import_id)
            result = _metadata(manifest, envelope, _active(root, connection))
        return result
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def activate_import(root, import_id, expected_active_hash):
    """Compare and swap only the source catalogue pointer, retaining every prior revision."""
    _directory(root, import_id)
    if not (Path(root) / 'catalogue-index.db').is_file():
        raise KeyError(import_id)
    with _connection(root, write=True) as connection:
        connection.execute('BEGIN IMMEDIATE')
        manifest, envelope = _indexed(root, connection, import_id)
        current = _active(root, connection)
        observed_hash = current['catalogue_hash'] if current else None
        if observed_hash != expected_active_hash:
            raise ActivationConflict('The active source catalogue changed. Reload the preview before activating.')
        connection.execute('INSERT OR REPLACE INTO active VALUES (1, ?)', (import_id,))
        connection.execute('INSERT INTO activations(import_id, previous_hash, catalogue_hash, activated_at) '
                           'VALUES (?, ?, ?, ?)', (import_id, observed_hash, envelope['catalogue_hash'],
                                                  datetime.now(timezone.utc).isoformat()))
        return _metadata(manifest, envelope, envelope)


def original_import(root, import_id):
    import_preview(root, import_id)  # All linked evidence must validate before any download.
    return _directory(root, import_id) / 'original.xlsx'
