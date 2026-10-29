"""Read-only source observation routes, separate from operational results."""
from contextlib import asynccontextmanager
import json

from fastapi import HTTPException, Query

from .source_jobs import SourceJobs


def install_inspection(app, store, registry=None):
    from .instrument_review import install_instrument_review
    install_instrument_review(app, store)
    jobs=SourceJobs(store.root,registry)
    app.state.source_jobs=jobs
    original=app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            try:
                yield
            finally:
                jobs.close()

    app.router.lifespan_context=lifespan

    @app.get('/api/source-lines')
    def source_lines():
        from ..workbench.source_lines import registry_line_models
        return {'items':registry_line_models(registry)}

    @app.get('/api/incidents/{incident_id}/inspection/analysis')
    def analysis(incident_id: str, record: str, revision: int = Query(...,ge=1), voltage_kv: int = 0,
                 mappings: str = Query('{}',max_length=12000), line_id: str = Query('',max_length=200),
                 line_model: str = Query('{}',max_length=32768), fault_loop: str = '',
                 projection_window: int | None = None, asserted_states: str = Query('{}',max_length=4096)):
        row=store.get(incident_id,revision)
        if row is None:
            raise HTTPException(404,'Revision not found.')
        def decode(raw,label):
            try:
                return json.loads(raw)
            except ValueError as exc:
                raise ValueError(label+' must be valid JSON choices.') from exc
        choices=decode(mappings,'Channel meanings')
        model=decode(line_model,'Line model')
        states=decode(asserted_states,'Asserted states')
        return jobs.request(row,record,dict(voltage_kv=voltage_kv,mappings=choices,line_id=line_id,line_model=model,
            fault_loop=fault_loop,projection_window=projection_window,asserted_states=states))

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


    @app.get('/api/incidents/{incident_id}/inspection/points')
    def inspection_cursor_points(incident_id: str, record: str, revision: int = Query(...,ge=1),
                                 channel_ids: str = Query(...,max_length=1024),
                                 indices: str = Query(...,max_length=512)):
        from ..workbench.source_inspection import inspection_points
        row=store.get(incident_id,revision)
        if row is None:
            raise HTTPException(404,'Revision not found.')
        try:
            channels=json.loads(channel_ids)
            positions=json.loads(indices)
        except ValueError as exc:
            raise ValueError('Channel IDs and sample indices must be valid JSON lists.') from exc
        return inspection_points(store.root,row,record,channels,positions)
