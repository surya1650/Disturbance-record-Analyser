"""Revision-scoped display names; no implicit electrical/terminal assignments."""
import json
import re
from pathlib import Path

from fastapi import HTTPException, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment

from .store import Conflict
from ..workbench.source_snapshot import line_facts


def read_end_names(store, row):
    with store.connect() as db:
        saved = db.execute('SELECT revision,version,payload FROM incident_end_names WHERE incident_id=? AND revision<=? ORDER BY revision DESC LIMIT 1',
                           (row['incident_id'], row['number'])).fetchone()
    raw = json.loads(saved['payload']) if saved else dict(names={}, record_ends={})
    records = [f for f in (row.get('bundle') or {}).get('files', []) if f['kind'] == 'comtrade']
    assignments = row['metadata'].get('assignments', {})
    ends, sources = {}, {}
    for file in records:
        declared = assignments.get(file['name'], {}).get('end') or file.get('terminal_end') or ''
        ends[file['name']] = declared or raw.get('record_ends', {}).get(file['name'], '')
        sources[file['name']] = 'operational assignment' if declared else 'user label' if ends[file['name']] else 'not assigned'
    line = line_facts(store.root, row)
    names, origins = {}, {}
    for end in ('S', 'R'):
        registered = line['terminals'].get(end)
        known = registered and registered != 'Not available'
        names[end] = registered if known else raw.get('names', {}).get(end, '')
        origins[end] = 'line definition' if known else 'user label' if names[end] else 'not provided'
    return dict(names=names, manual_names=raw.get('names', {}), record_ends=ends, name_sources=origins,
                record_end_sources=sources, revision=row['number'],
                version=saved['version'] if saved and saved['revision'] == row['number'] else 0)


def install_end_names(app, store):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS incident_end_names (incident_id TEXT NOT NULL,revision INTEGER NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(incident_id,revision))')

    @app.get('/api/incidents/{incident_id}/end-names')
    def get_names(incident_id: str, revision: int = Query(..., ge=1)):
        row = store.get(incident_id, revision)
        if row is None:
            raise HTTPException(404, 'Revision not found.')
        return read_end_names(store, row)

    @app.put('/api/incidents/{incident_id}/end-names')
    def save_names(incident_id: str, body: dict):
        if set(body) != {'revision', 'version', 'names', 'record_ends'}:
            raise ValueError('Supply revision, version, Sending/Receiving names and record labels only.')
        revision, version = body['revision'], body['version']
        if type(revision) is not int or revision < 1 or type(version) is not int or version < 0:
            raise ValueError('Use the displayed revision and label version.')
        row = store.get(incident_id, revision)
        if row is None:
            raise HTTPException(404, 'Revision not found.')
        names, ends = body['names'], body['record_ends']
        if not isinstance(names, dict) or set(names)-{'S', 'R'}:
            raise ValueError('Name only Sending end S and Receiving end R.')
        cleaned = {}
        for end in ('S', 'R'):
            value = names.get(end, '')
            if not isinstance(value, str) or len(value) > 120 or any(ord(c) < 32 for c in value):
                raise ValueError('Substation names must be text of at most 120 characters.')
            cleaned[end] = value.strip()
        allowed = {f['name'] for f in (row.get('bundle') or {}).get('files', []) if f['kind'] == 'comtrade'}
        if not isinstance(ends, dict) or set(ends)-allowed or any(v not in ('', 'S', 'R') for v in ends.values()):
            raise ValueError('Label only recordings in this revision as S, R or unassigned.')
        for name, assignment in row['metadata'].get('assignments', {}).items():
            if assignment.get('end') and name in ends and ends[name] != assignment['end']:
                raise ValueError(name+': change the operational end assignment before changing its display end.')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT version FROM incident_end_names WHERE incident_id=? AND revision=?', (incident_id, revision)).fetchone()
            if (previous['version'] if previous else 0) != version:
                raise Conflict('End names changed in another tab. Reload before saving.')
            db.execute('INSERT INTO incident_end_names VALUES(?,?,?,?) ON CONFLICT(incident_id,revision) DO UPDATE SET version=excluded.version,payload=excluded.payload',
                       (incident_id, revision, version+1, json.dumps(dict(names=cleaned, record_ends=ends))))
        return read_end_names(store, row)

    @app.get('/api/incidents/{incident_id}/named-report')
    def named_report(incident_id: str, revision: int = Query(..., ge=1), download: bool = False):
        row = store.get(incident_id, revision)
        saved = ((row or {}).get('result') or {}).get('report_path')
        if not saved:
            raise HTTPException(404, 'This revision has no operational report. Source reports remain in the viewer.')
        path = Path(saved).resolve()
        allowed = (store.root/'runs'/incident_id/str(revision)).resolve()
        if not path.is_relative_to(allowed) or not path.is_file():
            raise HTTPException(404, 'Report file is unavailable.')
        labels = read_end_names(store, row)
        header = Environment(autoescape=True).from_string('''<section style="padding:16px;border-bottom:1px solid #ccdce3;font:14px system-ui"><h2>Sending end — {{ p.names.S or 'Name not provided' }} → Receiving end — {{ p.names.R or 'Name not provided' }}</h2><p>Names: S {{ p.name_sources.S }}, R {{ p.name_sources.R }}. Display-label version {{ p.version }}; names do not authenticate physical identity.</p></section>''').render(p=labels)
        original = path.read_text(encoding='utf-8')
        rendered = re.sub(r'(<body\b[^>]*>)', lambda match: match[0]+header, original, count=1, flags=re.I)
        headers = {'Content-Disposition': f'attachment; filename="incident-r{revision}.html"'} if download else {}
        return HTMLResponse(rendered, headers=headers)
