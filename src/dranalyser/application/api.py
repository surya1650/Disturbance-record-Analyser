"""Loopback FastAPI interface. HTTP accepts work; durable workers perform analysis."""
from __future__ import annotations

import json
import hashlib
import secrets
import threading
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ..workbench.bundle import Bundle, BundleFile
from .intake import MAX_BYTES, Intake
from .store import Conflict, Store
from .watcher import Watcher
from .worker import Worker, registry_entries, validate_assignments


class Review(BaseModel):
    revision: int = Field(ge=1)
    line_id: str = ""
    assignments: dict[str, dict]


class LimitedBody:
    """Bound actual streamed request bytes before multipart parsing/spooling."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        size = 0

        async def limited():
            nonlocal size
            message = await receive()
            size += len(message.get('body', b''))
            if size > MAX_BYTES + 2 * 1024 * 1024:
                raise HTTPException(413, "Request exceeds the 400 MB upload limit.")
            return message

        await self.app(scope, limited, send)


def create_app(root="out/application", registry="data/registry", inbox=None, workers=2):
    store = Store(Path(root))
    registry = Path(registry).resolve()
    intake = Intake(store)
    watcher = Watcher(intake, inbox or store.root / 'inbox')
    token_path = store.root / 'api-token.txt'
    try:
        with token_path.open('x', encoding='ascii') as stream:
            stream.write(secrets.token_urlsafe(32))
    except FileExistsError:
        pass
    token = token_path.read_text(encoding='ascii').strip()

    @asynccontextmanager
    async def lifespan(app):
        stop = threading.Event()
        threads = [threading.Thread(target=Worker(store, registry).run, args=(stop,), daemon=True)
                   for _ in range(workers)]
        threads.append(threading.Thread(target=watcher.run, args=(stop,), daemon=True))
        for thread in threads:
            thread.start()
        yield
        stop.set()
        for thread in threads:
            thread.join(timeout=12)

    app = FastAPI(title="DR Analyser", version="0.2.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.state.store, app.state.intake, app.state.watcher = store, intake, watcher
    app.add_middleware(LimitedBody)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]', 'testserver'])

    @app.middleware('http')
    async def local_access(request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if origin and urlsplit(origin).netloc != request.headers.get('host'):
                return JSONResponse({'detail': 'Cross-origin writes are not accepted.'}, status_code=403)
            if not secrets.compare_digest(request.headers.get('x-dr-token', ''), token):
                return JSONResponse({'detail': 'A valid X-DR-Token header is required.'}, status_code=401)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409 if isinstance(exc, Conflict) else 400)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'detail': 'Incident or revision not found.'}, status_code=404)

    @app.exception_handler(zipfile.BadZipFile)
    async def bad_archive(request, exc):
        return JSONResponse({'detail': 'Invalid or incomplete ZIP archive.'}, status_code=400)

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'queued': store.summary().get('queued', 0)}

    @app.get('/api/config')
    def config():
        from ..workbench.channel_mapping import ANALOG_TARGETS, CANONICAL
        return {'token': token, 'inbox': str(watcher.inbox), 'data_directory': str(store.root),
                'registry_directory': str(registry), 'workers': workers, 'max_upload_mb': 400,
                'lines': registry_entries(registry), 'mapping_targets': {'analog': ANALOG_TARGETS, 'digital': CANONICAL},
                'native_sample_inspection': True, 'rx_input_review': True, 'stage_input_review': True,
                'stage_location': True}

    @app.get('/api/incidents')
    def incidents(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                  q: str = Query('', max_length=200), state: str = ''):
        return {'items': store.list(limit, offset, q, state), 'summary': store.summary()}

    @app.post('/api/intake', status_code=202)
    def upload(files: Annotated[list[UploadFile], File()], name: str = Form('Uploaded incident'),
               metadata: str | None = Form(None), incident_id: str | None = Form(None),
               expected_revision: int | None = Form(None), source: str = Form('manual')):
        if source not in ('manual', 'api'):
            raise ValueError('source must be manual or api')
        if len(files) > 2000:
            raise ValueError('Too many uploaded files.')
        if metadata is not None and len(metadata) > 1024 * 1024:
            raise ValueError('Metadata exceeds 1 MB.')
        row, duplicate = intake.ingest([(f.filename, f.file) for f in files], name=name,
            source=source, metadata=json.loads(metadata) if metadata is not None else None,
            incident_id=incident_id, expected=expected_revision)
        return {'incident_id': row['incident_id'], 'revision': row['number'],
                'state': row['state'], 'duplicate': duplicate}

    @app.get('/api/incidents/{incident_id}')
    def incident(incident_id: str, revision: int | None = Query(None, ge=1)):
        row = store.get(incident_id, revision)
        if not row:
            raise KeyError(incident_id)
        row.update(store.history(incident_id))
        return row

    @app.post('/api/incidents/{incident_id}/review', status_code=202)
    def review(incident_id: str, body: Review):
        row = store.get(incident_id)
        if not row:
            raise KeyError(incident_id)
        if row['number'] != body.revision or row['state'] != 'needs_review':
            raise Conflict('This revision is not awaiting review. Refresh the incident.')
        raw = row['bundle']
        bundle = Bundle(**{k: v for k, v in raw.items() if k != 'files'},
                        files=[BundleFile(**v) for v in raw['files']])
        meta = validate_assignments(bundle, {'line_id': body.line_id, 'assignments': body.assignments,
                                             'auto_analyse': True}, registry)
        meta.pop('incident_id', None)
        store.review(incident_id, body.revision, meta)
        return {'state': 'queued'}

    @app.post('/api/incidents/{incident_id}/retry', status_code=202)
    def retry(incident_id: str, revision: int = Query(..., ge=1)):
        store.retry(incident_id, revision)
        return {'state': 'queued'}

    @app.post('/api/incidents/{incident_id}/reanalyse', status_code=202)
    def reanalyse(incident_id: str, revision: int = Query(..., ge=1)):
        row = store.get(incident_id, revision)
        if not row:
            raise KeyError(incident_id)
        if row['state'] not in ('completed', 'attention', 'failed'):
            raise Conflict('Wait for this revision to finish before creating a new review.')
        metadata = {**row['metadata'], 'auto_analyse': False}
        fingerprint = hashlib.sha256(f'review:{incident_id}:{revision}'.encode()).hexdigest()
        new, duplicate = store.submit(name=row['name'], source='manual', files=row['files'],
            metadata=metadata, fingerprint=fingerprint, incident_id=incident_id, expected=revision)
        return {'incident_id': incident_id, 'revision': new['number'], 'duplicate': duplicate, 'state': new['state']}

    @app.get('/api/incidents/{incident_id}/report')
    def report(incident_id: str, revision: int | None = Query(None, ge=1), download: bool = False):
        row = store.get(incident_id, revision)
        path = (row or {}).get('result') or {}
        path = path.get('report_path')
        if not path:
            raise HTTPException(404, 'This revision has no report.')
        path = Path(path).resolve()
        if not path.is_relative_to(store.root / 'runs') or not path.is_file():
            raise HTTPException(404, 'Report file is unavailable.')
        return FileResponse(path, media_type='text/html',
                            filename=f'{incident_id}-r{row["number"]}.html' if download else None)

    @app.get('/api/integrations')
    def integrations():
        return {'inbox': str(watcher.inbox), 'receipts': store.receipts()}

    @app.get('/api/incidents/{incident_id}/navigator')
    def navigator(incident_id: str, revision: int = Query(..., ge=1)):
        row = store.get(incident_id, revision)
        saved = ((row or {}).get('result') or {}).get('navigator_path')
        if not saved:
            raise HTTPException(404, 'This revision has no navigator data. Review & rerun with the updated backend.')
        path = Path(saved).resolve()
        if not path.is_relative_to(store.root / 'runs') or not path.is_file():
            raise HTTPException(404, 'Navigator data is unavailable.')
        return FileResponse(path, media_type='application/json')

    @app.post('/api/integrations/scan')
    def scan():
        return {'received': watcher.scan()}

    @app.get('/api/incidents/{incident_id}/samples')
    def samples(incident_id: str, record: str, channel: str, start_s: float, end_s: float,
                revision: int = Query(..., ge=1)):
        from ..workbench.samples import sample_interval
        row = store.get(incident_id, revision)
        if row is None:
            raise HTTPException(404, 'Revision not found.')
        return sample_interval(store.root, row, record, channel, start_s, end_s)

    static = Path(__file__).with_name('static')
    app.mount('/static', StaticFiles(directory=static), name='static')

    @app.get('/')
    def index():
        return FileResponse(static / 'index.html')

    return app
