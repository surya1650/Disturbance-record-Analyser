"""Revision-bound playback declarations and immutable source display data."""
import json

from fastapi import HTTPException, Query

from .store import Conflict
from .end_names import read_end_names
from ..workbench.playback import clean_settings, playback_data


def install_playback(app, store, registry=None):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS playback_inputs (incident_id TEXT NOT NULL,revision INTEGER NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(incident_id,revision))')

    def get_row(identity, revision):
        row = store.get(identity, revision)
        if row is None:
            raise HTTPException(404, 'Revision not found.')
        return row

    @app.get('/api/incidents/{incident_id}/playback/channels')
    def channels(incident_id: str, record: str, revision: int = Query(..., ge=1)):
        from ..workbench.source_inspection import _source
        from ..workbench.source_display import timeline
        source, _ = _source(store.root, get_row(incident_id, revision), record)
        return dict(file=record, digital=[dict(id=c['key'], label=c['label']) for c in source['digital']],
                    timeline=timeline(source), source_sha256=source['source_sha256'])

    @app.get('/api/incidents/{incident_id}/playback')
    def get_settings(incident_id: str, revision: int = Query(..., ge=1)):
        get_row(incident_id, revision)
        with store.connect() as db:
            saved = db.execute('SELECT version,payload FROM playback_inputs WHERE incident_id=? AND revision=?', (incident_id, revision)).fetchone()
        return dict(version=saved['version'] if saved else 0, settings=json.loads(saved['payload']) if saved else None)

    @app.put('/api/incidents/{incident_id}/playback')
    def save_settings(incident_id: str, body: dict):
        if set(body) != {'revision', 'version', 'settings'} or type(body['revision']) is not int or body['revision'] < 1 or type(body['version']) is not int or body['version'] < 0:
            raise ValueError('Supply playback settings, revision and current nonnegative version.')
        row = get_row(incident_id, body['revision'])
        settings = clean_settings(store.root, row, body['settings'])
        names = read_end_names(store, row)
        for end, choice in settings['ends'].items():
            labelled = names['record_ends'].get(choice['record'])
            if labelled and labelled != end:
                raise ValueError(choice['record']+': correct its end label before playback at the opposite end.')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT version FROM playback_inputs WHERE incident_id=? AND revision=?', (incident_id, body['revision'])).fetchone()
            if (prior['version'] if prior else 0) != body['version']:
                raise Conflict('Playback inputs changed in another tab. Reopen this incident.')
            db.execute('INSERT INTO playback_inputs VALUES(?,?,?,?) ON CONFLICT(incident_id,revision) DO UPDATE SET version=excluded.version,payload=excluded.payload', (incident_id, body['revision'], body['version']+1, json.dumps(settings)))
        return dict(version=body['version']+1, settings=settings)

    @app.get('/api/incidents/{incident_id}/playback/data')
    def get_data(incident_id: str, revision: int = Query(..., ge=1)):
        row = get_row(incident_id, revision)
        saved = get_settings(incident_id, revision)
        if saved['settings'] is None:
            raise HTTPException(404, 'Choose the playback records and inputs first.')
        # Revalidate stored display labels and source hashes; never inherit a new revision.
        raw = {**saved['settings'], 'ends': {end: {k: v for k, v in c.items() if k != 'source_sha256'} for end, c in saved['settings']['ends'].items()}}
        checked = clean_settings(store.root, row, raw)
        if checked != saved['settings']:
            raise Conflict('Playback source binding changed. Review the inputs again.')
        names = read_end_names(store, row)
        if any(names['record_ends'].get(c['record']) not in ('', None, end) for end, c in checked['ends'].items()):
            raise Conflict('Recording-end labels changed. Review the playback selection.')
        data = playback_data(store.root, row, checked)
        inputs = {}
        with store.connect() as db:
            db.execute('BEGIN')
            for choice in checked['ends'].values():
                stored = db.execute('SELECT version,payload FROM diagram_inputs WHERE incident_id=? AND revision=? AND record=?', (incident_id, revision, choice['record'])).fetchone()
                inputs[choice['record']] = dict(version=stored['version'], **json.loads(stored['payload'])) if stored else dict(version=0, options=None, diagram={})
        data['source_inputs'] = inputs
        if data['line']['length_km'] is None:
            from ..workbench.source_lines import resolve_line
            models, issues = {}, []
            for stored in inputs.values():
                options = stored['options'] or {}
                if options.get('line_id') or options.get('line_model'):
                    try:
                        line = resolve_line(store.root, row, options, registry)
                        models[line['sha256']] = line
                    except ValueError as exc:
                        issues.append(str(exc))
            if len(models) == 1 and not issues:
                data['line'] = next(iter(models.values()))
            elif len(models) > 1 or issues:
                data['line']['provenance'] = 'Conflicting or unavailable declared line models. Review Inputs. '+' '.join(issues)
        return dict(version=saved['version'], presentation=names, **data)
