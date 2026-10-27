"""Read-only source observation routes, separate from operational results."""
from fastapi import HTTPException, Query


def install_inspection(app, store):
    @app.get('/api/incidents/{incident_id}/inspection')
    def inspection(incident_id: str, record: str, revision: int = Query(..., ge=1)):
        from ..workbench.source_inspection import inspection_record
        row = store.get(incident_id, revision)
        if row is None:
            raise HTTPException(404, 'Revision not found.')
        return inspection_record(store.root, row, record)

    @app.get('/api/incidents/{incident_id}/inspection/samples')
    def inspection_native(incident_id: str, record: str, channel_id: str, start_index: int, stop_index: int,
                          revision: int = Query(..., ge=1)):
        from ..workbench.source_inspection import inspection_samples
        row = store.get(incident_id, revision)
        if row is None:
            raise HTTPException(404, 'Revision not found.')
        return inspection_samples(store.root, row, record, channel_id, start_index, stop_index)

