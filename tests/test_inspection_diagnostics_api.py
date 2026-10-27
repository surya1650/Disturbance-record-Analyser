"""Background source diagnostics stay bounded and read-only."""
import copy
import time

from dranalyser.application.worker import Worker
from tests import test_application as app_fixtures
from tests import test_source_inspection as source_fixtures

environment=app_fixtures.environment
revision=source_fixtures.revision


def test_background_diagnostics_deduplicate_and_leave_revision_unchanged(environment,revision):
    client,app,_,registry=environment
    _,_,folder=revision
    r=client.post('/api/intake',files=[('files',(p.name,p.read_bytes())) for p in folder.iterdir()])
    identity=r.json()['incident_id']
    Worker(app.state.store,registry).once()
    before=copy.deepcopy(app.state.store.get(identity))
    history=app.state.store.history(identity)
    url=f'/api/incidents/{identity}/inspection/analysis'
    query=dict(revision=1,record='event.cfg',voltage_kv=132,mappings='{"D1":"AR_BLOCK"}')
    first=client.get(url,params=query)
    assert first.status_code==200,first.text
    body=first.json()
    assert body['status'] in ('pending','ready')
    deadline=time.monotonic()+10
    while body['status']=='pending' and time.monotonic()<deadline:
        time.sleep(.01)
        body=client.get(url,params=query).json()
    assert body['status']=='ready',body
    assert body['job_id']==first.json()['job_id']
    assert body['result']['ar']['status']=='Possible explanation'
    assert body['result']['options']['voltage_kv']==132
    assert app.state.store.get(identity)==before and app.state.store.history(identity)==history
    assert client.get(url,params={**query,'mappings':'{"D1":"IA"}'}).status_code==400
    dat=__import__('pathlib').Path(before['bundle']['root'])/'event.dat'
    dat.write_bytes(dat.read_bytes()+b'\n')
    assert client.get(url,params=query).status_code==400
    app.state.source_jobs.close()


def test_background_queue_has_a_real_bound(environment,revision,monkeypatch):
    import threading
    from dranalyser.application import source_jobs
    client,app,_,registry=environment
    _,_,folder=revision
    r=client.post('/api/intake',files=[('files',(p.name,p.read_bytes())) for p in folder.iterdir()])
    identity=r.json()['incident_id']
    Worker(app.state.store,registry).once()
    gate=threading.Event()
    original=source_jobs.diagnose_source
    def held(*args,**kwargs):
        assert gate.wait(10)
        return original(*args,**kwargs)
    monkeypatch.setattr(source_jobs,'diagnose_source',held)
    url=f'/api/incidents/{identity}/inspection/analysis'
    query=dict(revision=1,record='event.cfg')
    try:
        assert client.get(url,params={**query,'voltage_kv':0}).json()['status']=='pending'
        assert client.get(url,params={**query,'voltage_kv':132}).json()['status']=='pending'
        busy=client.get(url,params={**query,'voltage_kv':220}).json()
        assert busy['status']=='busy' and busy['detail']
    finally:
        gate.set()
        app.state.source_jobs.close()
