"""Intake/queue integration: durable revisions, safe retries, actual reports."""
from __future__ import annotations

import io
import json
import shutil
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest

pytest.importorskip('fastapi')
from fastapi.testclient import TestClient

from dranalyser.application.api import create_app
from dranalyser.application.intake import Intake, safe_name
from dranalyser.application.store import Store
from dranalyser.application.watcher import Watcher
from dranalyser.application.worker import Worker
from scripts.create_demo import create_demo


@pytest.fixture
def environment(tmp_path):
    source = create_demo(tmp_path / 'synthetic')
    registry = tmp_path / 'registry'
    registry.mkdir()
    shutil.copyfile(source / 'synthetic-line.yaml', registry / 'demo.yaml')
    app = create_app(tmp_path / 'app', registry, workers=0)
    client = TestClient(app)
    client.headers['X-DR-Token'] = client.get('/api/config').json()['token']
    return client, app, source, registry


def payload(root, end='S'):
    return [('files', (f'{end}/event.{ext}', (root / end / f'event.{ext}').read_bytes(), 'application/octet-stream'))
            for ext in ('cfg', 'dat')]


def test_manual_upload_review_report_late_remote_and_restart(environment):
    client, app, source, registry = environment
    response = client.post('/api/intake', files=payload(source), data={'name':'Synthetic local test'})
    assert response.status_code == 202, response.text
    identity = response.json()['incident_id']
    worker = Worker(app.state.store, registry)
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    assert row['state'] == 'needs_review'
    assert row['bundle']['files'][0]['ok']
    response = client.post(f'/api/incidents/{identity}/review', json={
        'revision':1,'line_id':'SYNTHETIC-DEMO','assignments':{'S/event.cfg':{'end':'S','role':'primary'}}})
    assert response.status_code == 202, response.text
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    assert row['state'] == 'completed', row
    assert 'km' in row['result']['location_text']
    first = client.get(f'/api/incidents/{identity}/report?revision=1').content
    assert b'<!DOCTYPE html>' in first
    response = client.post('/api/intake',files=payload(source,'R'),data={
        'incident_id':identity,'expected_revision':'1','metadata':json.dumps({
            'auto_analyse':True,'assignments':{'R/event.cfg':{'end':'R','role':'primary'}}})})
    assert response.status_code == 202, response.text
    assert response.json()['revision'] == 2
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    assert row['state']=='completed', row
    assert set(row['result']['used'])=={'S','R'}
    assert 'E5' in row['result']['location_text']
    assert client.get(f'/api/incidents/{identity}/report?revision=1').content == first
    reopened = Store(app.state.store.root)
    assert reopened.get(identity)['number']==2
    assert len(reopened.history(identity)['revisions'])==2


def test_automated_metadata_runs_and_retries_are_idempotent(environment):
    client, app, source, registry = environment
    files = payload(source) + payload(source,'R')
    data={'source':'api','metadata':(source/'intake.json').read_text()}
    a=client.post('/api/intake',files=files,data=data)
    b=client.post('/api/intake',files=files,data=data)
    assert a.status_code==b.status_code==202
    assert b.json()['duplicate'] and a.json()['incident_id']==b.json()['incident_id']
    assert len(app.state.store.list())==1
    Worker(app.state.store,registry).once()
    row=app.state.store.get(a.json()['incident_id'])
    assert row['state']=='completed', row
    assert row['bundle']['files'][0]['assignment_source']=='collector manifest'


def test_watch_folder_waits_for_ready_preserves_originals_and_deduplicates(environment):
    client, app, source, registry = environment
    target=app.state.watcher.inbox/'demo'
    shutil.copytree(source,target)
    assert app.state.watcher.scan()==0
    (target/'.ready').touch()
    assert app.state.watcher.scan()==1
    restarted=Watcher(Intake(Store(app.state.store.root)),app.state.watcher.inbox)
    assert restarted.scan()==0
    assert (target/'S/event.dat').exists()
    Worker(app.state.store,registry).once()
    assert app.state.store.list()[0]['state']=='completed'


def test_concurrent_workers_claim_once_and_stale_owner_cannot_publish(tmp_path):
    store=Store(tmp_path)
    job,_=store.submit(name='one',source='api',files=[],metadata={},fingerprint='one')
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims=list(pool.map(lambda _:Store(tmp_path).claim(),range(8)))
    taken=[r for r in claims if r]
    assert len(taken)==1
    with store.connect() as db:
        db.execute('UPDATE revisions SET lease=? WHERE id=?',(time.time()-1,job['id']))
    replacement=store.claim()
    assert replacement['owner'] != taken[0]['owner']
    assert not store.finish(taken[0],'completed',result={})
    assert store.finish(replacement,'attention',result={})


def test_bad_and_blocked_input_stays_visible_and_cannot_be_selected(environment):
    client,app,source,registry=environment
    response=client.post('/api/intake',files=[('files',('broken.cfg',b'not a CFG'))])
    identity=response.json()['incident_id']
    Worker(app.state.store,registry).once()
    row=app.state.store.get(identity)
    assert row['state']=='needs_review'
    assert 'no .dat' in row['bundle']['files'][0]['error']
    response=client.post(f'/api/incidents/{identity}/review',json={
        'revision':1,'assignments':{'broken.cfg':{'end':'S','role':'primary'}}})
    assert response.status_code==400
    assert app.state.store.get(identity)['state']=='needs_review'


@pytest.mark.parametrize('name',['../x.cfg','/etc/x.cfg','C:/x.cfg','a/../b.cfg','con.dat','a:b.cfg','x./a.cfg'])
def test_unsafe_names_are_refused(name):
    with pytest.raises(ValueError):
        safe_name(name)


def test_archive_traversal_and_collisions_are_rejected(environment):
    client,app,source,registry=environment
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('../escape.cfg','bad')
    response=client.post('/api/intake',files={'files':('bad.zip',archive.getvalue())})
    assert response.status_code==400
    assert not app.state.store.list()
    response=client.post('/api/intake',files=payload(source)+payload(source))
    assert response.status_code==400
    assert not app.state.store.list()


def test_stale_revision_conflict_preserves_previous_inputs(environment):
    client,app,source,registry=environment
    identity=client.post('/api/intake',files=payload(source)).json()['incident_id']
    response=client.post('/api/intake',files=payload(source,'R'),
                         data={'incident_id':identity,'expected_revision':'99'})
    assert response.status_code==409
    assert len(app.state.store.get(identity)['files'])==2


def test_write_token_origin_and_host_checks(environment):
    client,app,source,registry=environment
    assert client.post('/api/intake',files=payload(source),headers={'X-DR-Token':'wrong'}).status_code==401
    assert client.post('/api/intake',files=payload(source),headers={'Origin':'https://foreign.invalid'}).status_code==403
    assert client.get('/api/config',headers={'Host':'foreign.invalid'}).status_code==400
    assert client.get('/api/incidents/not-found').status_code==404
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200


def test_failed_job_retry_and_corrupt_blob_detection(environment):
    client,app,source,registry=environment
    identity=client.post('/api/intake',files=payload(source)).json()['incident_id']
    row=app.state.store.get(identity)
    blob=app.state.intake.blobs/row['files'][0]['sha256']
    original=blob.read_bytes()
    blob.write_bytes(b'corrupted')
    worker=Worker(app.state.store,registry)
    worker.once()
    assert app.state.store.get(identity)['state']=='failed'
    assert 'checksum' in app.state.store.get(identity)['error']
    blob.write_bytes(original)
    assert client.post(f'/api/incidents/{identity}/retry?revision=1').status_code==202
    worker.once()
    assert app.state.store.get(identity)['state']=='needs_review'


def test_queue_survives_reconstruction_and_conflicting_assignments_refuse(environment):
    client,app,source,registry=environment
    identity=client.post('/api/intake',files=payload(source)+payload(source,'R')).json()['incident_id']
    Worker(Store(app.state.store.root),registry).once()
    response=client.post(f'/api/incidents/{identity}/review',json={'revision':1,'assignments':{
        'S/event.cfg':{'end':'S','role':'primary'},'R/event.cfg':{'end':'S','role':'primary'}}})
    assert response.status_code==400
    assert app.state.store.get(identity)['state']=='needs_review'


def test_concurrent_duplicate_deliveries_create_one_incident(environment):
    client,app,source,registry=environment
    def send(_):
        streams=[(f'S/event.{ext}',io.BytesIO((source/'S'/f'event.{ext}').read_bytes()))
                 for ext in ('cfg','dat')]
        return Intake(Store(app.state.store.root)).ingest(streams,source='api')
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(send,range(6)))
    assert len({row['incident_id'] for row,duplicate in results})==1
    assert sum(not duplicate for row,duplicate in results)==1


def test_size_limit_applies_to_expanded_zip(environment,monkeypatch):
    from dranalyser.application import intake as intake_module
    client,app,source,registry=environment
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('huge.cfg','x'*10000)
    monkeypatch.setattr(intake_module,'MAX_BYTES',1000)
    response=client.post('/api/intake',files={'files':('large.zip',archive.getvalue())})
    assert response.status_code==400
    assert not app.state.store.list()


def test_settings_are_associated_to_their_terminal_and_ambiguous_exports_refuse(tmp_path,monkeypatch):
    from dranalyser.workbench.bundle import Bundle, BundleFile
    from dranalyser.workbench import settings as module
    monkeypatch.setattr(module,'load_settings',lambda p:p)
    bundle=Bundle('one',str(tmp_path),files=[BundleFile('S/local.rio','settings',True),
                                           BundleFile('R/remote.rio','settings',True)])
    found,errors=module.settings_for(bundle,{'S':'S/event.cfg','R':'R/event.cfg'})
    assert not errors
    assert found['S'].endswith('local.rio') and found['R'].endswith('remote.rio')
    bundle.files.append(BundleFile('unassigned.rio','settings',True))
    found,errors=module.settings_for(bundle,{'S':'S/event.cfg','R':'R/event.cfg'})
    assert 'terminal is ambiguous' in errors[0]
    bundle.files.append(BundleFile('S/another.rio','settings',True))
    found,errors=module.settings_for(bundle,{'S':'S/event.cfg','R':'R/event.cfg'})
    assert 'S' not in found
    assert any('multiple settings' in e for e in errors)


def test_review_again_creates_idempotent_revision_without_overwriting_report(environment):
    client,app,source,registry=environment
    identity=client.post('/api/intake',files=payload(source)+payload(source,'R'),
                         data={'metadata':(source/'intake.json').read_text()}).json()['incident_id']
    worker=Worker(app.state.store,registry)
    worker.once()
    first=client.get(f'/api/incidents/{identity}/report?revision=1').content
    a=client.post(f'/api/incidents/{identity}/reanalyse?revision=1')
    b=client.post(f'/api/incidents/{identity}/reanalyse?revision=1')
    assert a.status_code==b.status_code==202
    assert a.json()['revision']==b.json()['revision']==2
    assert b.json()['duplicate']
    worker.once()
    assert app.state.store.get(identity)['state']=='needs_review'
    assert client.get(f'/api/incidents/{identity}/report?revision=1').content==first
