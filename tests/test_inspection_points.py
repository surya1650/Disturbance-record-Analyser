"""Bounded cursor points read one immutable source for all channels and pins."""
import copy
import importlib
import json

import pytest

from tests.test_source_inspection import revision as revision
from tests.test_application import environment as environment
from dranalyser.application.worker import Worker


def points(*args):
    return importlib.import_module('dranalyser.workbench.source_inspection').inspection_points(*args)


def test_points_preserve_order_nulls_native_indices_times_and_single_read(revision,monkeypatch):
    root,row,_=revision
    module=importlib.import_module('dranalyser.workbench.source_inspection')
    original=module._source
    calls=[]
    def counted(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(module,'_source',counted)
    before=copy.deepcopy(row)
    out=points(root,row,'event.cfg',['D1','A1'],[3,0,2])
    assert len(calls)==1
    assert [c['id'] for c in out['channels']]==['D1','A1']
    assert out['channels'][0]['samples']==[[3,.0026,0],[0,0,0],[2,.0017,None]]
    assert out['channels'][1]['samples']==[[3,.0026,27],[0,0,21],[2,.0017,None]]
    assert out['source_sha256'] and out['revision']==1 and out['file']=='event.cfg'
    assert out['indices']==[3,0,2] and row==before
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize(('channels','indices'),[
    ([],[0]),(['A1']*2,[0]),(['A1']*9,[0]),(['A1'],[]),(['A1'],list(range(18))),
    (['A1'],[0,0]),(['A1'],[True]),(['A1'],[1.0]),(['A1'],[-1]),(['A1'],[4]),
    (['BAD'],[0]),('A1',[0]),(['A1'],'0'),([True],[0]),([{}],[0])])
def test_points_reject_invalid_or_oversized_choices(revision,channels,indices):
    root,row,_=revision
    with pytest.raises(ValueError):
        points(root,row,'event.cfg',channels,indices)


def test_points_keep_index_only_coordinates_and_reject_changed_source(revision):
    import hashlib
    root,row,folder=revision
    dat=folder/'event.dat'
    dat.write_text(dat.read_text().replace('3,1700','3,800'))
    for f in row['files']:
        f['sha256']=hashlib.sha256((folder/f['name']).read_bytes()).hexdigest()
    out=points(root,row,'event.cfg',['D1'],[0,2])
    assert out['channels'][0]['samples']==[[0,None,0],[2,None,None]]
    dat.write_text(dat.read_text()+'\n')
    with pytest.raises(ValueError,match='checksum'):
        points(root,row,'event.cfg',['D1'],[0])
    with pytest.raises(ValueError):
        points(root,row,'../event.cfg',['D1'],[0])


def test_points_api_bounded_json_choices_without_result_or_mutation(environment,revision):
    client,app,_,registry=environment
    _,_,folder=revision
    identity=client.post('/api/intake',files=[('files',(p.name,p.read_bytes())) for p in folder.iterdir()]).json()['incident_id']
    Worker(app.state.store,registry).once()
    before=client.get(f'/api/incidents/{identity}').json()
    url=f'/api/incidents/{identity}/inspection/points'
    query=dict(revision=1,record='event.cfg',channel_ids='["A1","D1"]',indices='[0,2]')
    out=client.get(url,params=query)
    assert out.status_code==200,out.text
    assert out.json()['channels'][1]['samples']==[[0,0,0],[2,.0017,None]]
    for name,value in [('indices','[true]'),('indices','['),('channel_ids','["A1","A1"]')]:
        error=client.get(url,params={**query,name:value})
        assert error.status_code==400 and error.json()['detail']
    assert client.get(url,params={**query,'revision':99}).status_code==404
    assert client.get(f'/api/incidents/{identity}').json()==before
