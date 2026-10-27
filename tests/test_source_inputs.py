"""Explicit line/polarity inputs remain source-bound assumptions."""
import copy
import hashlib

import pytest

from dranalyser.workbench.source_diagnostics import diagnose_source, diagnostic_identity
from dranalyser.workbench.source_events import digital_evidence, trip_ar
from tests import test_source_inspection as fixtures

revision=fixtures.revision


def line_file(registry,name='line.yaml',identifier='CHOSEN',end=20):
    registry.mkdir(exist_ok=True)
    path=registry/name
    path.write_text(f'id: {identifier}\nname: Supplied corridor\nkv: 132\nmodel_review_required: true\nterminals:\n  S: {{substation: Near}}\n  R: {{substation: Far}}\nsections:\n- {{from_km: 0, to_km: {end}, r1: 0.1, x1: 0.4}}\n')
    return path


def test_selected_registry_line_is_explicit_provisional_and_hash_bound(revision,tmp_path):
    root,row,_=revision
    registry=tmp_path/'registry'
    path=line_file(registry)
    choices={'line_id':'CHOSEN','fault_loop':'AB','projection_window':0}
    first=diagnose_source(root,row,'event.cfg',choices,registry=registry)
    line=first['snapshot']['line']
    assert line['name']=='Supplied corridor' and line['length_km']==20
    assert line['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert line['parameter_status']=='provisional'
    assert first['authorizes_location'] is False
    path.write_text(path.read_text().replace('to_km: 20','to_km: 25'))
    second=diagnostic_identity(root,row,'event.cfg',choices,registry=registry)
    assert second['job_id']!=first['job_id']


def test_registry_ids_cannot_select_foreign_paths_or_duplicate_ids(revision,tmp_path):
    root,row,_=revision
    registry=tmp_path/'registry'
    line_file(registry)
    for identifier in ('../line.yaml','ABSENT'):
        with pytest.raises(ValueError):
            diagnose_source(root,row,'event.cfg',{'line_id':identifier},registry=registry)
    line_file(registry,'duplicate.yaml')
    with pytest.raises(ValueError,match='exactly one'):
        diagnose_source(root,row,'event.cfg',{'line_id':'CHOSEN'},registry=registry)


def test_custom_missing_line_fields_do_not_prevent_source_report(revision):
    root,row,_=revision
    choices={'line_model':{'x1_ohm_per_km':.4,'provenance':'User declaration; full length not supplied'},'fault_loop':'AB'}
    out=diagnose_source(root,row,'event.cfg',choices)
    assert out['snapshot']['line']['length_km'] is None
    assert out['snapshot']['line']['constants']['x1_ohm_per_km']==.4
    assert out['snapshot']['sections']['observed']
    assert out['methods']['location']['status']=='Not available'
    other=copy.deepcopy(choices)
    other['line_model']['length_km']=50
    assert diagnostic_identity(root,row,'event.cfg',choices)['job_id']!=diagnostic_identity(root,row,'event.cfg',other)['job_id']


@pytest.mark.parametrize('options',[{'line_id':'X','line_model':{'length_km':10}},
    {'line_model':{'length_km':True}}, {'line_model':{'filename':'C:/secret'}},
    {'asserted_states':{'A1':0}}, {'asserted_states':{'D1':True}}, {'asserted_states':{'D1':2}},
    {'projection_window':-1}, {'fault_loop':'INVALID'}])
def test_malformed_analysis_input_is_a_specific_local_request_error(revision,options):
    root,row,_=revision
    with pytest.raises(ValueError):
        diagnose_source(root,row,'event.cfg',options)


def test_active_low_state_keeps_unknown_gaps_and_explicit_provenance(revision):
    root,row,_=revision
    out=diagnose_source(root,row,'event.cfg',{'mappings':{'D1':'TRIP'},'asserted_states':{'D1':0}})
    c=out['digital_evidence'][0]
    assert c['asserted_state']==0 and c['assertion_source']=='source-analysis choice'
    assert c['active_samples']==2 and c['unknown_samples']==1
    assert c['first_active_index']==0 and c['falling_count']==0
    assert out['trip']['status']=='Observed indication'


def test_cfg_normal_state_does_not_silently_become_assertion_authority(revision):
    root,row,folder=revision
    cfg=folder/'event.cfg'
    cfg.write_text(cfg.read_text().replace('1,TRIP,,,0','1,TRIP,,,1'))
    for entry in row['files']:
        entry['sha256']=hashlib.sha256((folder/entry['name']).read_bytes()).hexdigest()
    out=diagnose_source(root,row,'event.cfg',{'mappings':{'D1':'TRIP'}})
    c=out['digital_evidence'][0]
    assert c['declared_normal_state']==1
    assert c['assertion_source']=='assumed high state'
    assert not c['interpretation_available']
    assert out['trip']['status']=='Not available'


def test_active_low_close_followed_by_trip_uses_assertion_edges():
    source={'axis':{'elapsed_s':[0,.001,.002,.003]},'header_inventory':[],
        'digital':[{'key':'D1','label':'close','states':[1,0,1,1]}, {'key':'D2','label':'trip','states':[1,1,1,0]}]}
    rows=digital_evidence(source,{'D1':'AR_CLOSE','D2':'TRIP'},asserted_states={'D1':0,'D2':0})
    trip,ar=trip_ar(rows)
    assert trip['status']=='Observed indication'
    assert ar['status']=='Possible explanation' and 'followed' in ar['text']
    source['digital'][1]['states']=[1,None,0,0]
    rows=digital_evidence(source,{'D1':'AR_CLOSE','D2':'TRIP'},asserted_states={'D1':0,'D2':0})
    assert trip_ar(rows)[1]['status']=='Not available'


def test_line_and_asserted_state_choices_invalidate_completed_jobs(revision,tmp_path):
    from dranalyser.application.source_jobs import SourceJobs
    from tests.test_source_diagnostics_review import wait_ready
    root,row,_=revision
    jobs=SourceJobs(root)
    try:
        base=wait_ready(jobs,row)
        choices={'asserted_states':{'D1':0},'line_model':{'length_km':50,'x1_ohm_per_km':.4},'fault_loop':'AB'}
        import time
        deadline=time.monotonic()+10
        while True:
            body=jobs.request(row,'event.cfg',choices)
            if body['status']!='pending' or time.monotonic()>deadline:
                break
            time.sleep(.01)
        assert body['status']=='ready',body
        assert body['job_id']!=base['job_id']
        assert body['result']['digital_evidence'][0]['asserted_state']==0
        assert body['result']['digital_evidence'][0]['active_samples']==2
        assert body['result']['snapshot']['line']['length_km']==50
    finally:
        jobs.close()


def test_revised_line_report_reuses_unchanged_source_models(revision,monkeypatch):
    from dranalyser.application.source_jobs import SourceJobs
    from dranalyser.workbench import source_models
    from tests.test_source_diagnostics_review import wait_ready
    root,row,_=revision
    jobs=SourceJobs(root)
    try:
        original=wait_ready(jobs,row)
        def no_reanalysis(*args,**kwargs):
            raise RuntimeError('Unchanged native signal models should be reusable for a line choice.')
        monkeypatch.setattr(source_models,'analyse_source',no_reanalysis)
        import time
        deadline=time.monotonic()+10
        while True:
            body=jobs.request(row,'event.cfg',{'line_model':{'length_km':50,'x1_ohm_per_km':.4}})
            if body['status']!='pending' or time.monotonic()>deadline:
                break
            time.sleep(.01)
        assert body['status']=='ready',body
        assert body['result']['fit_coverage']==original['result']['fit_coverage']
        assert body['result']['snapshot']['line']['length_km']==50
    finally:
        jobs.close()


@pytest.mark.parametrize('model',[[],False])
def test_empty_wrong_shape_line_model_cannot_be_silently_ignored(revision,model):
    root,row,_=revision
    with pytest.raises(ValueError,match='model'):
        diagnose_source(root,row,'event.cfg',{'line_model':model})


def analytic_revision(tmp_path):
    """Public exact sinusoidal source: Z=(1+j4)ohm on each phase, no fault truth."""
    import math
    folder=tmp_path/'runs'/'public-model'/'1'/'owner'/'records'
    folder.mkdir(parents=True)
    cfg=folder/'analytic.cfg'
    names=['VA','VB','VC','IA','IB','IC']
    header=['PUBLIC SYNTHETIC,MODEL,2013','6,6A,0D']
    for i,name in enumerate(names):
        header.append(f'{i+1},{name},{"ABC"[i%3]},,{"V" if i<3 else "A"},1,0,0,-1000000,1000000,1,1,P')
    header+=['50','1','1200,241','01/01/2020,00:00:00.000000','01/01/2020,00:00:00.000000','ASCII','1']
    cfg.write_text('\n'.join(header)+'\n')
    rows=[]
    for i in range(241):
        theta=2*math.pi*50*i/1200
        angles=[theta,theta-2*math.pi/3,theta+2*math.pi/3]
        current=[math.sqrt(2)*10*math.cos(t) for t in angles]
        voltage=[math.sqrt(2)*10*(math.cos(t)-4*math.sin(t)) for t in angles]
        rows.append(','.join(map(str,[i+1,i*1e6/1200,*voltage,*current])))
    cfg.with_suffix('.dat').write_text('\n'.join(rows)+'\n')
    row=dict(incident_id='public-model',number=1,state='needs_review',result=None,
        files=[dict(name=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=p.stat().st_size) for p in folder.iterdir()],
        bundle=dict(root=str(folder),files=[dict(name=cfg.name,kind='comtrade',data_file='analytic.dat',ok=True,blocked=False)]))
    return tmp_path,row,folder


def test_native_source_pipeline_projects_known_declared_model_without_authority(tmp_path):
    root,row,_=analytic_revision(tmp_path)
    choices={'line_model':{'length_km':50,'x1_ohm_per_km':.4,'r1_ohm_per_km':.1,'provenance':'Public analytic test model'},
        'fault_loop':'AB','projection_window':0}
    out=diagnose_source(root,row,'analytic.cfg',choices)
    point=out['selected_projection']
    assert point['status']=='Conditional model projection'
    assert point['distance_km']==pytest.approx(10,abs=1e-5)
    assert complex(*out['derived_quantities']['windows'][0]['loops']['AB']['impedance_ohm'])==pytest.approx(1+4j,abs=1e-5)
    assert point['eligible_overlay'] and not point['authorizes_location']
    assert out['snapshot']['selected_projection']['distance_km']==point['distance_km']
    assert out['options']['fault_loop']=='AB' and out['options']['projection_window']==0


def test_line_snapshot_cannot_mix_two_configured_file_versions(revision,tmp_path,monkeypatch):
    from dranalyser.workbench import source_snapshot
    root,row,_=revision
    registry=tmp_path/'registry'
    path=line_file(registry)
    original_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    real_metadata=source_snapshot.inspection_record
    def edit_after_metadata(*args,**kwargs):
        result=real_metadata(*args,**kwargs)
        path.write_text(path.read_text().replace('to_km: 20','to_km: 25'))
        return result
    monkeypatch.setattr(source_snapshot,'inspection_record',edit_after_metadata)
    out=diagnose_source(root,row,'event.cfg',{'line_id':'CHOSEN'},registry=registry)
    assert out['line_sha256']==original_hash
    assert out['snapshot']['line']['sha256']==original_hash
    assert out['snapshot']['line']['length_km']==20


def test_pending_choices_are_frozen_before_the_caller_changes_them(revision,monkeypatch):
    import threading
    import time
    from dranalyser.application import source_jobs
    root,row,_=revision
    gate=threading.Event()
    original=source_jobs.diagnose_source
    def held(*args,**kwargs):
        assert gate.wait(10)
        return original(*args,**kwargs)
    monkeypatch.setattr(source_jobs,'diagnose_source',held)
    choices={'asserted_states':{'D1':1},'line_model':{'length_km':20,'x1_ohm_per_km':.4}}
    old=copy.deepcopy(choices)
    jobs=source_jobs.SourceJobs(root)
    def ready(options):
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            body=jobs.request(row,'event.cfg',options)
            if body['status']!='pending':
                assert body['status']=='ready',body
                return body
            time.sleep(.01)
        pytest.fail('Pending choice job timed out')
    try:
        first=jobs.request(row,'event.cfg',choices)
        choices['asserted_states']['D1']=0
        choices['line_model']['length_km']=30
        second=jobs.request(row,'event.cfg',choices)
        assert first['job_id']!=second['job_id']
        gate.set()
        a,b=ready(old)['result'],ready(choices)['result']
        assert (a['digital_evidence'][0]['asserted_state'],a['snapshot']['line']['length_km'])==(1,20)
        assert (b['digital_evidence'][0]['asserted_state'],b['snapshot']['line']['length_km'])==(0,30)
    finally:
        gate.set()
        jobs.close()
