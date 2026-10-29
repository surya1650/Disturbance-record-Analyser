"""Reviewed CT/VT ratings create traceable copies; originals remain immutable."""
import io
import zipfile

from fastapi import HTTPException, Query
from fastapi.responses import Response

from .intake import Intake
from ..workbench.ratio_inputs import prepare_ratio_copy, required_ratios
from ..workbench.source_inspection import _source


def install_instrument_review(app, store):
    def revision_row(incident_id, revision):
        if type(revision) is not int or not 1 <= revision <= 2147483647:
            raise ValueError('Supply a revision number from 1 to 2147483647.')
        row = store.get(incident_id, revision)
        if row is None:
            raise HTTPException(404, 'Revision not found.')
        return row

    def prepare(incident_id, body, *, saving_allowed=True):
        allowed = {'record', 'revision', 'review', 'save'} if saving_allowed else {'record', 'revision', 'review'}
        if not isinstance(body, dict) or set(body)-allowed:
            raise ValueError('Unsupported instrument-review request field.')
        if not isinstance(body.get('record'), str) or type(body.get('save', False)) is not bool:
            raise ValueError('Supply a recording and explicit save choice.')
        row = revision_row(incident_id, body.get('revision'))
        prepared = prepare_ratio_copy(store.root, row, body['record'], body.get('review'))
        return row, prepared

    @app.get('/api/incidents/{incident_id}/instrument-review')
    def instrument_requirements(incident_id: str, record: str,
                                revision: int = Query(..., ge=1, le=2147483647)):
        row = revision_row(incident_id, revision)
        source, item = _source(store.root, row, record)
        return dict(record=record, revision=revision, record_hash=item.get('content_hash'),
                    source_sha256=source['source_sha256'],
                    required_ratios=required_ratios(source),
                    blocking_findings=[f for f in item.get('flags', []) if f.startswith('[BLOCK ')],
                    source_samples=source['sample_count'],
                    note='Enter verified primary/secondary ratings in A for currents or V for voltages. '
                         'Unknown ratios do not prevent raw waveform inspection.')

    @app.post('/api/incidents/{incident_id}/instrument-review')
    def instrument_review(incident_id: str, body: dict):
        row, prepared = prepare(incident_id, body)
        result = {key: prepared[key] for key in ('flags', 'blocked', 'reviewed_record')}
        result['note'] = 'All conformance checks were rerun on a marked reviewed copy; originals are unchanged.'
        if body.get('save', False):
            streams = [(name, io.BytesIO(content)) for name, content in prepared['files'].items()]
            original_assignment = dict(row['metadata'].get('assignments', {}).get(body['record'], {}))
            original_assignment.update(end='', role='excluded')
            job, duplicate = Intake(store).ingest(
                streams, name=row['name'], source='instrument-review',
                incident_id=incident_id, expected=row['number'],
                metadata={'auto_analyse': False, 'assignments': {body['record']: original_assignment}})
            result.update(incident_id=incident_id, revision=job['number'], duplicate=duplicate)
        return result

    @app.post('/api/incidents/{incident_id}/instrument-review/export')
    def export_instrument_review(incident_id: str, body: dict):
        _, prepared = prepare(incident_id, body, saving_allowed=False)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, content in prepared['files'].items():
                archive.writestr(name, content)
        return Response(stream.getvalue(), media_type='application/zip',
                        headers={'Content-Disposition': 'attachment; filename="reviewed-instrument-ratios.zip"'})
