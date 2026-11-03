"""Immutable, revision-bound reader reports; existing technical results stay intact."""
import copy
import datetime as dt
import hashlib
import json
import re
import shutil
import uuid

from fastapi import HTTPException, Query
from fastapi.responses import FileResponse

from .store import Conflict


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _build_model(root, row, records, event_inputs):
    from ..workbench.incident_report import build_incident_report
    return build_incident_report(root, row, records=records, event_inputs=event_inputs)


def _render_model(model):
    from ..workbench.incident_report import render_incident_report
    return render_incident_report(model)


def install_incident_reports(app, store):
    with store.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS reader_reports (
            report_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, revision INTEGER NOT NULL,
            created_at TEXT NOT NULL, bindings TEXT NOT NULL, files TEXT NOT NULL,
            FOREIGN KEY(incident_id,revision) REFERENCES revisions(incident_id,number))''')
        db.execute('''CREATE INDEX IF NOT EXISTS reader_report_history
            ON reader_reports(incident_id,revision,created_at)''')

    def row_for(incident_id, revision):
        if type(revision) is not int or not 1 <= revision <= 2147483647:
            raise ValueError('Supply a valid incident revision before generating a report.')
        row = store.get(incident_id, revision)
        if row is None:
            raise HTTPException(404, 'Incident revision not found.')
        return row

    def inputs_for(db, row):
        saved = db.execute('SELECT version,inputs,bindings FROM event_study_inputs WHERE incident_id=? AND revision=?',
                           (row['incident_id'], row['number'])).fetchone()
        if not saved:
            return None
        return dict(version=saved['version'], inputs=json.loads(saved['inputs']), bindings=json.loads(saved['bindings']))

    def binding_for(row, saved):
        return dict(version=1, incident_id=row['incident_id'], revision=row['number'],
                    files={f['name']: f['sha256'] for f in row['files']},
                    metadata_sha256=_digest(row.get('metadata') or {}),
                    result_sha256=_digest(row.get('result') or {}),
                    bundle_sha256=_digest(row.get('bundle') or {}),
                    event_inputs_sha256=_digest(saved))

    def artifact(saved, kind):
        report_id = saved['report_id']
        folder = (store.root / 'runs' / saved['incident_id'] / str(saved['revision']) / 'reader-reports' / report_id).resolve()
        files = json.loads(saved['files'])
        entry = files[kind]
        path = (folder / entry['name']).resolve()
        if (not path.is_relative_to(folder) or not folder.is_relative_to(store.root / 'runs')
                or not path.is_file() or path.is_symlink()
                or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']):
            raise HTTPException(404, 'The saved report artifact is unavailable or changed.')
        return path

    def response_for(saved, row, current_inputs):
        model_path = artifact(saved, 'data')
        artifact(saved, 'html')
        prefix = f'/api/incidents/{row["incident_id"]}/incident-report/{saved["report_id"]}'
        with store.connect() as db:
            history = db.execute('''SELECT report_id,created_at FROM reader_reports
                WHERE incident_id=? AND revision=? ORDER BY created_at DESC,report_id DESC LIMIT 20''',
                (row['incident_id'], row['number'])).fetchall()
        base = f'/api/incidents/{row["incident_id"]}/incident-report/'
        return dict(report_id=saved['report_id'], revision=saved['revision'], created_at=saved['created_at'],
                    model=json.loads(model_path.read_text(encoding='utf-8')),
                    is_current=json.loads(saved['bindings']) == binding_for(row, current_inputs),
                    urls=dict(html=prefix+'/html', data=prefix+'/data'),
                    history=[dict(report_id=item['report_id'], created_at=item['created_at'],
                        urls=dict(html=base+item['report_id']+'/html', data=base+item['report_id']+'/data')) for item in history])

    @app.get('/api/incidents/{incident_id}/incident-report')
    def latest(incident_id: str, revision: int = Query(..., ge=1, le=2147483647)):
        row = row_for(incident_id, revision)
        with store.connect() as db:
            saved = db.execute('SELECT * FROM reader_reports WHERE incident_id=? AND revision=? ORDER BY created_at DESC,report_id DESC LIMIT 1',
                               (incident_id, revision)).fetchone()
            current_inputs = inputs_for(db, row)
        if not saved:
            return dict(report=None, revision=revision, state='not_generated')
        return response_for(saved, row, current_inputs)

    @app.post('/api/incidents/{incident_id}/incident-report', status_code=201)
    def generate(incident_id: str, body: dict):
        if set(body) - {'revision', 'records'}:
            raise ValueError('Report generation accepts revision and optional selected recordings only.')
        row = row_for(incident_id, body.get('revision'))
        if row['state'] in ('queued', 'running'):
            raise Conflict('Wait for recording parsing or analysis to finish before generating the report.')
        records = body.get('records')
        if records is not None and (not isinstance(records, list) or not 1 <= len(records) <= 2
                                   or any(not isinstance(name, str) or not name or len(name) > 1000 for name in records)
                                   or len(set(records)) != len(records)):
            raise ValueError('Select one or two different recordings from this incident revision.')
        available = {f['name'] for f in (row.get('bundle') or {}).get('files', []) if f.get('kind') == 'comtrade'}
        if records is not None and any(name not in available for name in records):
            raise ValueError('Select recordings listed in this incident revision, not another file or path.')
        with store.connect() as db:
            original_inputs = inputs_for(db, row)
        bindings = binding_for(row, original_inputs)
        model = _build_model(store.root, copy.deepcopy(row), records, copy.deepcopy(original_inputs))
        report_id = uuid.uuid4().hex
        created_at = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat(timespec='microseconds')
        model['generation'] = dict(report_id=report_id, created_at=created_at, timezone='Asia/Calcutta',
                                   bindings=bindings, model_sha256=_digest(model))
        rendered = _render_model(model)
        folder = store.root / 'runs' / incident_id / str(row['number']) / 'reader-reports' / report_id
        folder.mkdir(parents=True, exist_ok=False)
        published = False
        try:
            data = _json(model).encode('utf-8')
            html = rendered.encode('utf-8')
            (folder / 'report.json').write_bytes(data)
            (folder / 'report.html').write_bytes(html)
            files = dict(data=dict(name='report.json', sha256=hashlib.sha256(data).hexdigest()),
                         html=dict(name='report.html', sha256=hashlib.sha256(html).hexdigest()))
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                current = store.decode(db.execute('''SELECT r.*,i.name,i.source FROM revisions r
                    JOIN incidents i ON i.id=r.incident_id WHERE r.incident_id=? AND r.number=?''',
                    (incident_id, row['number'])).fetchone())
                latest_revision = db.execute('SELECT MAX(number) FROM revisions WHERE incident_id=?', (incident_id,)).fetchone()[0]
                current_inputs = inputs_for(db, current) if current else None
                if (current is None or latest_revision != row['number'] or current['state'] in ('queued', 'running')
                        or binding_for(current, current_inputs) != bindings):
                    raise Conflict('The incident or report inputs changed while generating. Generate again from the current revision.')
                db.execute('INSERT INTO reader_reports VALUES (?,?,?,?,?,?)',
                           (report_id, incident_id, row['number'], created_at, _json(bindings), _json(files)))
                saved = db.execute('SELECT * FROM reader_reports WHERE report_id=?', (report_id,)).fetchone()
            published = True
            return response_for(saved, current, current_inputs)
        except Exception:
            if not published:
                shutil.rmtree(folder)
            raise

    def saved_for(incident_id, report_id):
        if not re.fullmatch('[0-9a-f]{32}', report_id):
            raise HTTPException(404, 'Report generation not found.')
        with store.connect() as db:
            saved = db.execute('SELECT * FROM reader_reports WHERE incident_id=? AND report_id=?',
                               (incident_id, report_id)).fetchone()
        if saved is None:
            raise HTTPException(404, 'Report generation not found.')
        return saved

    @app.get('/api/incidents/{incident_id}/incident-report/{report_id}/html')
    def report_html(incident_id: str, report_id: str, download: bool = False):
        saved = saved_for(incident_id, report_id)
        return FileResponse(artifact(saved, 'html'), media_type='text/html',
                            filename=f'incident-{incident_id}-r{saved["revision"]}.html' if download else None)

    @app.get('/api/incidents/{incident_id}/incident-report/{report_id}/data')
    def report_data(incident_id: str, report_id: str, download: bool = False):
        saved = saved_for(incident_id, report_id)
        return FileResponse(artifact(saved, 'data'), media_type='application/json',
                            filename=f'incident-{incident_id}-r{saved["revision"]}.json' if download else None)
