"""The main app exposes read-only inspection before assignment or analysis."""
import copy

from dranalyser.application.worker import Worker
from tests import test_application as app_fixtures
from tests import test_source_inspection as source_fixtures

environment = app_fixtures.environment
revision = source_fixtures.revision


def test_inspection_api_without_result_does_not_change_revision_or_history(environment, revision):
    client,app,_,registry = environment
    _,_,folder = revision
    response = client.post('/api/intake',files=[('files',(p.name,p.read_bytes())) for p in folder.iterdir()])
    identity = response.json()['incident_id']
    assert Worker(app.state.store,registry).once()
    row = client.get(f'/api/incidents/{identity}').json()
    assert row['state'] == 'needs_review' and row['result'] is None
    before = copy.deepcopy(row)
    url = f'/api/incidents/{identity}/inspection'
    query = dict(revision=1,record='event.cfg')
    result = client.get(url,params=query)
    assert result.status_code == 200, result.text
    assert result.json()['sample_count'] == 4
    assert result.json()['operational_eligibility']['state'] == 'needs_review'
    out = client.get(url+'/samples',params={**query,'channel_id':'D1','start_index':0,'stop_index':4})
    assert out.status_code == 200
    assert [s[2] for s in out.json()['samples']] == [0,1,None,0]
    assert client.get(f'/api/incidents/{identity}').json() == before
    assert client.get(url,params={'record':'event.cfg'}).status_code == 422
    assert client.get(url,params={**query,'revision':99}).status_code == 404
    assert client.get(url,params={**query,'record':'../event.cfg'}).status_code == 400
    assert client.get(url+'/samples',params={**query,'channel_id':'D1','start_index':-1,'stop_index':1}).status_code == 400
    review = client.post(f'/api/incidents/{identity}/review',json={'revision':1,'assignments':{},'line_id':''})
    assert review.status_code == 400
    assert client.get(f'/api/incidents/{identity}').json() == before


def test_cfg_only_record_returns_local_reason(environment,revision):
    client,app,_,registry = environment
    _,_,folder = revision
    p = folder/'event.cfg'
    result = client.post('/api/intake',files=[('files',(p.name,p.read_bytes()))]).json()
    Worker(app.state.store,registry).once()
    response = client.get(f"/api/incidents/{result['incident_id']}/inspection",params=dict(revision=1,record=p.name))
    assert response.status_code == 200
    assert response.json()['status'] == 'cfg_only'
    assert response.json()['issues'] and response.json()['sample_count'] == 0
