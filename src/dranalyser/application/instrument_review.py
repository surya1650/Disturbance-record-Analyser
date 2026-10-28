"""Preview missing-ratio questions and create an explicit reviewed-copy revision."""
import io

from fastapi import HTTPException

from .intake import Intake
from ..workbench.ratio_inputs import prepare_ratio_copy


def install_instrument_review(app, store):
    @app.post('/api/incidents/{incident_id}/instrument-review')
    def instrument_review(incident_id: str, body: dict):
        if set(body)-{'record', 'revision', 'review', 'save'}:
            raise ValueError('Unsupported ratio-review request field.')
        revision, record, save = body.get('revision'), body.get('record'), body.get('save', False)
        if type(revision) is not int or revision < 1 or not isinstance(record, str) or type(save) is not bool:
            raise ValueError('Supply a recording, positive revision number and explicit save choice.')
        row = store.get(incident_id, revision)
        if row is None:
            raise HTTPException(404, 'Revision not found.')
        prepared = prepare_ratio_copy(store.root, row, record, body.get('review'))
        result = {key: prepared[key] for key in ('flags', 'blocked', 'reviewed_record')}
        if save:
            streams = [(name, io.BytesIO(content)) for name, content in prepared['files'].items()]
            original_assignment = dict(row['metadata'].get('assignments', {}).get(record, {}))
            original_assignment.update(end='', role='excluded')
            job, duplicate = Intake(store).ingest(streams, name=row['name'], source='instrument-review',
                incident_id=incident_id, expected=revision,
                metadata={'auto_analyse': False, 'assignments': {record: original_assignment}})
            result.update(incident_id=incident_id, revision=job['number'], duplicate=duplicate)
        return result
