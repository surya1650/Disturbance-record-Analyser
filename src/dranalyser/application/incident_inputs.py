"""Save explicit line facts on the same incident and exact original recordings."""
import copy

from fastapi import HTTPException, Query

from .intake import metadata_value
from .store import Conflict
from ..workbench.incident_inputs import (incident_line_missing, line_input_fingerprint,
                                        prepare_incident_line, validate_incident_line)


def install_incident_inputs(app, store):
    def row_for(incident_id, revision):
        if type(revision) is not int or not 1 <= revision <= 2147483647:
            raise ValueError('Supply the current incident revision.')
        row = store.get(incident_id, revision)
        if row is None:
            raise HTTPException(404, 'Incident revision not found.')
        return row

    @app.get('/api/incidents/{incident_id}/line-inputs')
    def line_inputs(incident_id: str, revision: int = Query(..., ge=1, le=2147483647)):
        row = row_for(incident_id, revision)
        entry = validate_incident_line(row)
        return dict(revision=revision, line_id=entry.get('line_id'), review=entry.get('review'),
            missing=incident_line_missing(entry),
            note='Saved line facts do not alter the uploaded files or create another capture.')

    @app.post('/api/incidents/{incident_id}/line-inputs', status_code=202)
    def save_line_inputs(incident_id: str, body: dict):
        if set(body)-{'revision', 'review'}:
            raise ValueError('Supply the current revision and explicit line review only.')
        row = row_for(incident_id, body.get('revision'))
        latest = store.get(incident_id)
        if latest['number'] != row['number'] or row['state'] in ('queued', 'running'):
            raise Conflict('Wait for the current revision or reopen the incident before saving inputs.')
        entry, assignments = prepare_incident_line(row, body.get('review'))
        metadata = metadata_value(dict(copy.deepcopy(row['metadata']), line_id=entry['line_id'],
            incident_line=entry, assignments=assignments, auto_analyse=False))
        metadata.pop('incident_id', None)
        new, duplicate = store.submit(name=row['name'], source='line-input-review', files=row['files'],
            metadata=metadata, fingerprint=line_input_fingerprint(incident_id, row['number'], metadata),
            incident_id=incident_id, expected=row['number'])
        return dict(incident_id=incident_id, revision=new['number'], line_id=entry['line_id'],
            missing=incident_line_missing(entry), state=new['state'], duplicate=duplicate)
