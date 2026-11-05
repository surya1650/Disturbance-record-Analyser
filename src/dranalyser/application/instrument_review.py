"""Save source-bound instrument inputs on the same recording; keep originals immutable."""
import copy
import hashlib
import io
import json
import zipfile

from fastapi import HTTPException, Query
from fastapi.responses import Response

from .store import Conflict
from .intake import Intake
from ..workbench.ratio_inputs import (prepare_ratio_copy, prepare_ratio_update, required_ratios,
                                    primary_reviewable_channels, review_basis)
from ..workbench.measurement_basis import measurement_basis_hint
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
        allowed = {'record', 'revision', 'review', 'save', 'mode'} if saving_allowed else {'record', 'revision', 'review', 'mode'}
        if not isinstance(body, dict) or set(body)-allowed:
            raise ValueError('Unsupported instrument-review request field.')
        if not isinstance(body.get('record'), str) or type(body.get('save', False)) is not bool:
            raise ValueError('Supply a recording and explicit save choice.')
        row = revision_row(incident_id, body.get('revision'))
        mode = body.get('mode', 'same-record')
        if mode not in ('same-record', 'copy'):
            raise ValueError('Choose same-record instrument inputs or an explicit reviewed copy.')
        builder = prepare_ratio_copy if not saving_allowed or mode == 'copy' else prepare_ratio_update
        prepared = builder(store.root, row, body['record'], body.get('review'))
        return row, prepared

    @app.get('/api/incidents/{incident_id}/instrument-review')
    def instrument_requirements(incident_id: str, record: str,
                                revision: int = Query(..., ge=1, le=2147483647)):
        row = revision_row(incident_id, revision)
        source, item = _source(store.root, row, record)
        original = dict(source, header_inventory=source.get('recorded_header_inventory', source.get('header_inventory', [])))
        applied = source.get('instrument_review') or {}
        return dict(record=record, revision=revision, record_hash=item.get('content_hash'),
                    source_sha256=source['source_sha256'],
                    required_ratios=required_ratios(source, item=item),
                    reviewable_ratios=required_ratios(original, item=item),
                    primary_reviewable_channels=primary_reviewable_channels(original['header_inventory']),
                    measurement_basis_hint=measurement_basis_hint(source),
                    applied_review=copy.deepcopy(applied), applied_review_basis=review_basis(applied),
                    blocking_findings=[f for f in item.get('flags', []) if f.startswith('[BLOCK ')],
                    source_samples=source['sample_count'],
                    note='Explicitly declare PRIMARY values after the recorded gains, or enter actual secondary CT/VT ratings in A or V. '
                         'Amplitude alone does not establish the measurement basis. Instrument scaling remains unverified.')

    @app.post('/api/incidents/{incident_id}/instrument-review')
    def instrument_review(incident_id: str, body: dict):
        row, prepared = prepare(incident_id, body)
        mode = body.get('mode', 'same-record')
        result = {key: prepared[key] for key in ('flags', 'blocked', 'reviewed_record')}
        result.update(record=body['record'], save_mode=mode, applied_review=prepared['review'])
        result['applied_review_basis'] = review_basis(prepared['review'])
        result['note'] = ('All conformance checks were rerun using source-bound inputs on this recording; original files are unchanged.'
                          if mode == 'same-record' else 'Conformance was rerun on an explicitly requested reviewed copy; originals are unchanged.')
        if body.get('save', False) and mode == 'same-record':
            if store.get(incident_id)['number'] != row['number']:
                raise Conflict('This incident changed. Refresh before updating instrument inputs.')
            metadata = copy.deepcopy(row['metadata'])
            assignments = metadata.setdefault('assignments', {})
            assignment = assignments.setdefault(body['record'], dict(end='', role='excluded'))
            if assignment.get('instrument_review') == prepared['review']:
                return dict(result, incident_id=incident_id, revision=row['number'], duplicate=True)
            assignment['instrument_review'] = prepared['review']
            fingerprint = hashlib.sha256(json.dumps(dict(kind='same-record-instrument-inputs',
                target=incident_id, parent_revision=row['number'], files=row['files'], metadata=metadata),
                sort_keys=True, allow_nan=False).encode()).hexdigest()
            job, duplicate = store.submit(name=row['name'], source='instrument-inputs', files=row['files'],
                metadata=metadata, fingerprint=fingerprint, incident_id=incident_id, expected=row['number'])
            result.update(incident_id=incident_id, revision=job['number'], duplicate=duplicate)
        elif body.get('save', False):
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
