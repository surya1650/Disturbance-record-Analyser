"""Revision-bound event display inputs, with optimistic concurrent-edit checks."""
import json

from fastapi import HTTPException, Query

from .store import Conflict
from ..workbench.event_study import build_event_report, prepare_inputs, record_inventory
from ..workbench.source_diagnostics import normalise_options
from ..workbench.source_inspection import _source
from ..workbench.source_regions import auto_regions


def install_event_study(app,store):
    with store.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS event_study_inputs (
            incident_id TEXT NOT NULL, revision INTEGER NOT NULL, version INTEGER NOT NULL,
            inputs TEXT NOT NULL, bindings TEXT NOT NULL,
            PRIMARY KEY(incident_id,revision),
            FOREIGN KEY(incident_id,revision) REFERENCES revisions(incident_id,number))''')

    def row_for(incident_id,revision):
        if type(revision) is not int or not 1<=revision<=2147483647:
            raise ValueError('Supply an integer revision from 1 to 2147483647.')
        row=store.get(incident_id,revision)
        if row is None:
            raise HTTPException(404,'Revision not found.')
        return row

    def request(body,fields):
        if not isinstance(body,dict) or set(body)-set(fields):
            raise ValueError('Unsupported event-study request field.')

    @app.post('/api/incidents/{incident_id}/event-study/regions')
    def select_regions(incident_id:str,body:dict):
        request(body,{'revision','record','mappings','asserted_states'})
        row=row_for(incident_id,body.get('revision'))
        record=body.get('record')
        source,item=_source(store.root,row,record)
        options=normalise_options(dict(mappings=body.get('mappings',{}),asserted_states=body.get('asserted_states',{})),source)
        selected=auto_regions(source,item,mappings=options['mappings'],asserted_states=options.get('asserted_states',{}))
        return dict(selected,file=record,revision=row['number'],source_sha256=source['source_sha256'],sample_count=source['sample_count'])

    @app.get('/api/incidents/{incident_id}/event-study')
    def get_event_study(incident_id:str,revision:int=Query(...,ge=1,le=2147483647)):
        row=row_for(incident_id,revision)
        with store.connect() as db:
            saved=db.execute('SELECT * FROM event_study_inputs WHERE incident_id=? AND revision=?',
                (incident_id,revision)).fetchone()
        inputs=json.loads(saved['inputs']) if saved else dict(same_event_confirmed=False,ends={})
        return dict(revision=revision,version=saved['version'] if saved else 0,inputs=inputs,
            source_bindings=json.loads(saved['bindings']) if saved else {},records=record_inventory(row),
            note='Select records and explicit source-local [start, stop) sample intervals. Exact native times and counts are returned by the report. Two ends require same-event confirmation; successive captures from one relay belong at one end.')

    @app.put('/api/incidents/{incident_id}/event-study')
    def put_event_study(incident_id:str,body:dict):
        request(body,{'revision','expected_version','inputs'})
        row=row_for(incident_id,body.get('revision'))
        version=body.get('expected_version')
        if type(version) is not int or not 0<=version<=2147483646:
            raise ValueError('Expected version must be an integer from 0 to 2147483646.')
        inputs,sources=prepare_inputs(store.root,row,body.get('inputs'))
        bindings={end:source['source_sha256'] for end,(source,_) in sources.items()}
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT MAX(number) FROM revisions WHERE incident_id=?',(incident_id,)).fetchone()[0]
            saved=db.execute('SELECT version FROM event_study_inputs WHERE incident_id=? AND revision=?',
                (incident_id,row['number'])).fetchone()
            if current!=row['number'] or (saved['version'] if saved else 0)!=version:
                raise Conflict('The incident or event inputs changed. Refresh before saving.')
            db.execute('''INSERT INTO event_study_inputs VALUES (?,?,?,?,?)
                ON CONFLICT(incident_id,revision) DO UPDATE SET
                version=excluded.version,inputs=excluded.inputs,bindings=excluded.bindings''',
                (incident_id,row['number'],version+1,json.dumps(inputs,allow_nan=False),json.dumps(bindings)))
        return dict(revision=row['number'],version=version+1,inputs=inputs,source_bindings=bindings)

    @app.post('/api/incidents/{incident_id}/event-study/report')
    def event_study_report(incident_id:str,body:dict):
        request(body,{'revision','inputs'})
        row=row_for(incident_id,body.get('revision'))
        return build_event_report(store.root,row,body.get('inputs'))
