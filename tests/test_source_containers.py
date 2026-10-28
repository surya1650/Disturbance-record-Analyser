"""Explicit CFF framing never searches binary payload for marker-like bytes."""
import copy
import hashlib
import struct

import pytest

from dranalyser.application.worker import Worker
from dranalyser.comtrade.source_observations import load_source
from tests.test_application import environment as environment
from tests.test_source_recovery import record


def container(tmp_path,kind='ASCII',*,analog=1,digital=1,n=3,dat_marker=None,tail=b''):
    cfg=record(tmp_path,kind=kind,analog=analog,digital=digital,n=n)
    marker=kind if dat_marker is None else dat_marker
    path=tmp_path/'source.cff'
    path.write_bytes(b'--- file type: CFG ---\n'+cfg.read_bytes()+
        f'--- file type: DAT {marker} ---\n'.encode()+cfg.with_suffix('.dat').read_bytes()+tail)
    return path


@pytest.mark.parametrize('kind',['ASCII','BINARY','BINARY32','FLOAT32'])
@pytest.mark.parametrize('analog',[0,1])
def test_explicit_container_preserves_observations_and_original_identity(tmp_path,kind,analog):
    path=container(tmp_path,kind,analog=analog)
    out=load_source(path)
    assert out['sample_count']==3 and out['digital'][0]['states']==[0,1,0]
    assert [c['values'] for c in out['channels']]==([[21,23,25]] if analog else [])
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert out['source_sha256']=={path.name:digest}
    assert out['content_hash']==digest and 'original CFF' in out['content_hash_basis']
    assert len(out['header_inventory'])==analog+1
    assert out['recorded_times']['start']=='01/01/2020,00:00:00.000000'
    assert not out['authorizes_location'] and not out['alignment_eligible']


@pytest.mark.parametrize('kind',['ASCII','BINARY','BINARY32','FLOAT32'])
def test_recognised_text_tail_starts_only_at_declared_binary_boundary(tmp_path,kind):
    path=container(tmp_path,kind,tail=b'\n--- file type: HDR ---\nPublic notes\n--- file type: INF ---\nMore notes\n')
    out=load_source(path)
    assert out['sample_count']==3
    assert out['digital'][0]['states']==[0,1,0]


def test_binary_marker_like_payload_bytes_are_observations_not_sections(tmp_path):
    path=container(tmp_path,'BINARY',analog=16,digital=0)
    cfg=(tmp_path/'source.cfg').read_bytes()
    payload=bytearray((tmp_path/'source.dat').read_bytes())
    marker=b'\n--- file type: HDR ---\nxx'
    payload[8:8+len(marker)]=marker
    path.write_bytes(b'--- file type: CFG ---\n'+cfg+b'--- file type: DAT BINARY ---\n'+payload)
    out=load_source(path)
    assert out['sample_count']==3
    assert out['channels'][0]['values'][0]==2*struct.unpack('<h',payload[8:10])[0]+1


@pytest.mark.parametrize('marker',['FUTURE','BINARY'])
def test_unknown_or_conflicting_dat_marker_refuses_but_keeps_header(tmp_path,marker):
    path=container(tmp_path,'ASCII',dat_marker=marker)
    out=load_source(path)
    assert out['status']=='unsupported' and out['sample_count']==0
    assert out['header_inventory'][0]['label']=='A1'
    assert any('format' in issue.lower() for issue in out['issues'])
    assert set(out['source_sha256'])=={path.name}


def test_missing_dat_keeps_independently_readable_cfg_metadata(tmp_path):
    cfg=record(tmp_path)
    path=tmp_path/'only.cff'
    path.write_bytes(b'--- file type: CFG ---\n'+cfg.read_bytes())
    out=load_source(path)
    assert out['status']=='cfg_only' and out['sample_count']==0
    assert out['header_inventory'][0]['a']=='2'
    assert 'missing' in ' '.join(out['issues']).lower()


def test_binary_ambiguous_tail_refuses_without_hiding_header(tmp_path):
    path=container(tmp_path,'BINARY',tail=b'not framed metadata')
    out=load_source(path)
    assert out['status']=='unsupported' and out['header_inventory']
    assert 'trailing' in ' '.join(out['issues']).lower()


def test_container_truncation_uses_same_safe_complete_prefix(tmp_path):
    path=container(tmp_path,'BINARY',n=4)
    path.write_bytes(path.read_bytes()[:-1])
    out=load_source(path)
    assert out['sample_count']==3 and out['recovery']['opaque_bytes']==11
    assert out['axis']['status']=='withheld'


def test_main_application_inspects_cff_without_operational_result_or_mutation(environment,tmp_path):
    client,app,_,registry=environment
    path=container(tmp_path,'ASCII')
    identity=client.post('/api/intake',files=[('files',(path.name,path.read_bytes()))]).json()['incident_id']
    assert Worker(app.state.store,registry).once()
    before=copy.deepcopy(client.get(f'/api/incidents/{identity}').json())
    assert before['state']=='needs_review' and before['result'] is None
    result=client.get(f'/api/incidents/{identity}/inspection',params=dict(revision=1,record=path.name))
    assert result.status_code==200,result.text
    out=result.json()
    assert out['sample_count']==3 and len(out['inventory'])==2
    assert 'original CFF' in out['content_hash_basis']
    assert set(out['source_sha256'])=={path.name}
    assert client.get(f'/api/incidents/{identity}').json()==before


def test_malformed_dat_separator_is_an_explicit_local_error(tmp_path):
    path=container(tmp_path)
    path.write_bytes(path.read_bytes().replace(b'DAT ASCII ---',b'DAT ASCII --'))
    out=load_source(path)
    assert out['status']=='unsupported' and out['header_inventory']
    assert 'malformed' in ' '.join(out['issues']).lower()


def test_dat_marker_may_rely_on_the_explicit_cfg_format(tmp_path):
    out=load_source(container(tmp_path,'BINARY',dat_marker=''))
    assert out['sample_count']==3 and out['digital'][0]['states']==[0,1,0]
