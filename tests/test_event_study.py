"""Event summaries preserve native evidence and cannot manufacture location."""
import copy
import math
from pathlib import Path

import pytest

from dranalyser.workbench import event_study as study
from test_application import environment as environment, payload
from dranalyser.application.worker import Worker


def source(station='Sending',device='relay-1'):
    times=[i/1000 for i in range(240)]
    channels=[]
    for n,meaning in enumerate(('VA','VB','VC','IA','IB','IC')):
        values=[math.sqrt(2)*(100 if n<3 else 1)*(1 if i<100 else .5 if n<3 else 5)*math.sin(2*math.pi*50*t+n) for i,t in enumerate(times)]
        channels.append(dict(key='A'+str(n+1),label=meaning,values=values,units='V' if n<3 else 'A'))
    return dict(station=station,device=device,source_sha256={'event.cfg':station+'-cfg','event.dat':station+'-dat'},
        sample_count=len(times),nominal_frequency_hz=50,axis={'elapsed_s':times},channels=channels,
        digital=[dict(key='D1',label='Any Trip',states=[0]*130+[1]*110),
                 dict(key='D2',label='AR close',states=[1]*240)],header_inventory=[])


def inputs(pair=False):
    out=dict(same_event_confirmed=pair,ends={'S':dict(record='S/event.cfg',substation='Sending SS',pre=[0,80],fault=[100,220])})
    if pair:
        out['ends']['R']=dict(record='R/event.cfg',substation='Receiving SS',pre=[0,80],fault=[100,220])
    return out


@pytest.fixture
def model(monkeypatch):
    sources={'S/event.cfg':source(),'R/event.cfg':source('Receiving','relay-2')}
    monkeypatch.setattr(study,'_source',lambda root,row,file:(sources[file],{}))
    return sources,dict(incident_id='incident',number=1,files=[],bundle={})


def test_combined_phases_native_complete_regions_and_changes(model):
    _,row=model
    report=study.build_event_report('.',row,inputs(True))
    assert set(report['ends'])=={'S','R'}
    for end in report['ends'].values():
        assert [c['meaning'] for c in end['groups']['voltage']]==['VA','VB','VC']
        assert [c['meaning'] for c in end['groups']['current']]==['IA','IB','IC']
        values={v['meaning']:v for v in end['phase_values']}
        assert values['VA']['pre_rms']==pytest.approx(100)
        assert values['VA']['fault_rms']==pytest.approx(50)
        assert values['VA']['change_percent']==pytest.approx(-50)
        assert values['IA']['pre_rms']==pytest.approx(1)
        assert values['IA']['fault_rms']==pytest.approx(5)
        assert values['IA']['change_percent']==pytest.approx(400)
        assert values['VA']['pre_windows']==60
        assert values['VA']['fault_windows']==100
        assert end['origin_s']==.1
        assert end['sample_count']==240
        assert sum(len(c['trace'])+len(c['rms_trace']) for g in end['groups'].values() for c in g)<=6000
    assert report['distance']['km_from_S'] is None
    assert not report['authorizes_location']


def test_missing_and_short_regions_never_cross_a_boundary(model):
    _,row=model
    chosen=inputs()
    chosen['ends']['S'].update(pre=[0,15],fault=None)
    end=study.build_event_report('.',row,chosen)['ends']['S']
    assert all(v['pre_rms'] is None and v['fault_rms'] is None for v in end['phase_values'])
    assert end['origin_s'] is None
    assert end['groups']['voltage'][0]['trace']


def test_raw_units_zero_missing_values_and_ambiguous_mapping(model):
    sources,row=model
    capture=sources['S/event.cfg']
    capture['channels'][0]['values']=[0.]*240
    capture['channels'][3]['units']='raw counts'
    capture['channels'][3]['values'][100:220]=[None]*120
    capture['channels'].append(dict(capture['channels'][1],key='A99'))
    end=study.build_event_report('.',row,inputs())['ends']['S']
    values={v['meaning']:v for v in end['phase_values']}
    assert values['VA']['pre_rms']==values['VA']['fault_rms']==0
    assert values['VA']['change_percent'] is None
    assert values['IA']['units']=='raw counts' and values['IA']['fault_rms'] is None
    assert 'VB' not in values
    assert any('ambiguous' in note for note in end['insights'])


def test_explicit_source_meanings_and_polarity_reach_event_observations(model):
    sources,row=model
    sources['S/event.cfg']['channels'][0]['label']='vendor_U1'
    chosen=inputs()
    chosen['ends']['S'].update(mappings={'A1':'VA','D1':'TRIP'},asserted_states={'D1':0})
    normalised,_=study.prepare_inputs('.',row,chosen)
    assert normalised['ends']['S']['mappings']=={'A1':'VA','D1':'TRIP'}
    assert normalised['ends']['S']['asserted_states']=={'D1':0}
    end=study.build_event_report('.',row,chosen)['ends']['S']
    value=next(v for v in end['phase_values'] if v['meaning']=='VA')
    assert value['label']=='vendor_U1' and value['pre_rms']==pytest.approx(100)
    assert value['mapping_source']=='source-analysis choice'
    event=end['digital']['events'][0]
    assert event['meaning']=='TRIP' and event['kind']=='cleared'
    assert event['asserted_state']==0 and event['assertion_source']=='source-analysis choice'
    assert event['interpretation_available']


@pytest.mark.parametrize('mappings,states',[
    ({'A99':'VA'},{}),({'D1':'VA'},{}),({'A1':'VA','A2':'VA'},{}),
    ({'A1':'not-a-meaning'},{}),({}, {'A1':1}),({}, {'D1':True}),({}, {'D1':2}),
])
def test_invalid_or_duplicate_display_choices_are_refused(model,mappings,states):
    _,row=model
    chosen=inputs()
    chosen['ends']['S'].update(mappings=mappings,asserted_states=states)
    with pytest.raises(ValueError):
        study.prepare_inputs('.',row,chosen)


@pytest.mark.parametrize('meaning,units,declared',[
    ('VA','A (CFG-declared, unverified)',''),('VA','kA',''),
    ('IA','V (CFG-declared, unverified)',''),('IA','kV',''),
    ('VA','raw counts','A'),('IA','A (CFG-declared, unverified)','kV'),
])
def test_conflicting_physical_quantities_withheld_with_original_provenance(model,meaning,units,declared):
    sources,row=model
    capture=sources['S/event.cfg']
    channel=next(c for c in capture['channels'] if c['label']==meaning)
    channel['units']=units
    capture['header_inventory']=[dict(id=channel['key'],declared_units=declared)]
    original=copy.deepcopy(capture)
    chosen=inputs()
    chosen['ends']['S']['mappings']={channel['key']:meaning}
    end=study.build_event_report('.',row,chosen)['ends']['S']
    assert meaning not in {v['meaning'] for v in end['phase_values']}
    assert meaning not in {c['meaning'] for group in end['groups'].values() for c in group}
    withheld=end['withheld_phases'][0]
    assert withheld['id']==channel['key'] and withheld['units']==units
    assert withheld['declared_units']==declared
    assert withheld['mapping_source']=='source-analysis choice'
    assert 'mapping conflicts with recorded' in withheld['reason']
    assert any('review meaning/scaling' in note and 'source-analysis choice' in note for note in end['insights'])
    assert capture==original


@pytest.mark.parametrize('mutation,match',[
    (lambda x:x.update(same_event_confirmed=False),'Confirm both'),
    (lambda x:x['ends']['R'].update(record='S/event.cfg'),'same capture'),
    (lambda x:x['ends']['S'].update(pre=[True,80]),'native indices'),
    (lambda x:x['ends']['S'].update(fault=[50,220]),'finish before'),
    (lambda x:x['ends']['S'].update(unknown=1),'unsupported'),
    (lambda x:x['ends']['S'].update(relay_distance={'km':1,'reference':'S','evidence':''}),'nonempty'),
    (lambda x:x['ends']['S'].update(relay_distance={'km':10**400,'reference':'S','evidence':'relay'}),'finite km'),
])
def test_invalid_or_ambiguous_event_declarations(model,mutation,match):
    _,row=model
    chosen=inputs(True)
    mutation(chosen)
    with pytest.raises(ValueError,match=match):
        study.prepare_inputs('.',row,chosen)


def test_successive_same_relay_captures_are_not_opposite_ends(model):
    sources,row=model
    sources['R/event.cfg'].update(station=' Sending ',device='RELAY-1')
    with pytest.raises(ValueError,match='same station and relay'):
        study.prepare_inputs('.',row,inputs(True))


def test_digital_brackets_initial_active_and_conditional_interpretation(model):
    _,row=model
    digital=study.build_event_report('.',row,inputs())['ends']['S']['digital']
    assert digital['total_events']==1
    edge=digital['events'][0]
    assert edge['id']=='D1' and edge['kind']=='asserted'
    assert edge['index']==130 and edge['sample_bracket']==[129,130]
    assert edge['source_bracket_s']==[.129,.130]
    assert edge['relative_fault_s']==pytest.approx(.03)
    assert any('assertion time is unknown' in s for s in digital['insights'])
    assert any('breaker opening requires' in s for s in digital['insights'])


def test_existing_location_requires_same_selected_records_and_eligible_line(model,monkeypatch):
    _,row=model
    facts=dict(length_km=100,provenance='frozen line',location=dict(text='25.000 km from Sending by E5',km_from_S=25,overlay_eligible=True))
    monkeypatch.setattr(study,'line_facts',lambda root,row:facts)
    row['result']=dict(used={'S':'S/event.cfg','R':'R/event.cfg'},location_text='25.000 km from Sending by E5')
    chosen=inputs(True)
    chosen['ends']['R']['relay_distance']=dict(km=73,reference='R',evidence='Relay event front panel')
    report=study.build_event_report('.',row,chosen)
    assert report['distance']['km_from_S']==25
    assert report['distance']['method']=='E5'
    assert report['relay_distances'][0]['reported_from_S_km']==27
    assert report['relay_distances'][0]['delta_to_calculated_km']==2
    assert study.build_event_report('.',row,inputs())['distance']['km_from_S'] is None
    facts['location']['overlay_eligible']=False
    assert study.build_event_report('.',row,chosen)['distance']['km_from_S'] is None
    facts['location']['overlay_eligible']=True
    facts['parameter_status']='provisional'
    assert study.build_event_report('.',row,chosen)['distance']['km_from_S'] is None
    facts['parameter_status']='declared'
    row['result']['location_text']='25.000 km from Sending'
    assert study.build_event_report('.',row,chosen)['distance']['km_from_S'] is None


def test_unchanged_source_and_no_reported_distance_inference(model):
    sources,row=model
    original=copy.deepcopy(sources)
    report=study.build_event_report('.',row,inputs(True))
    assert sources==original
    assert report['relay_distances']==[]


def test_optional_post_region_and_out_of_line_relay_distance(model,monkeypatch):
    _,row=model
    chosen=inputs()
    chosen['ends']['S'].update(fault=[100,180],post=[180,240],relay_distance=dict(km=101,reference='R',evidence='Relay display'))
    monkeypatch.setattr(study,'line_facts',lambda root,row:dict(length_km=100,provenance='declared line',location=dict(text='Not available')))
    report=study.build_event_report('.',row,chosen)
    value=report['ends']['S']['phase_values'][0]
    assert value['post_rms']==pytest.approx(50)
    assert value['post_windows']==40
    assert report['relay_distances'][0]['reported_from_S_km'] is None
    assert report['relay_distances'][0]['delta_to_calculated_km'] is None
    assert 'exceeds' in report['relay_distances'][0]['reason']
    chosen['ends']['S']['post']=[170,240]
    with pytest.raises(ValueError,match='post-fault interval'):
        study.prepare_inputs('.',row,chosen)


def _incident(environment):
    client,app,source,registry=environment
    response=client.post('/api/intake',files=payload(source)+payload(source,'R'))
    assert response.status_code==202,response.text
    identity=response.json()['incident_id']
    assert Worker(app.state.store,registry).once()
    return client,app,identity


def test_event_api_saved_bindings_concurrent_inputs_and_frozen_bytes(environment):
    client,app,identity=_incident(environment)
    base=f'/api/incidents/{identity}/event-study'
    initial=client.get(base+'?revision=1')
    assert initial.status_code==200,initial.text
    assert initial.json()['version']==0
    assert {r['file'] for r in initial.json()['records']}=={'S/event.cfg','R/event.cfg'}
    body=dict(revision=1,expected_version=0,inputs=inputs(True))
    body['inputs']['ends']['S']['mappings']={'A1':'ignore'}
    saved=client.put(base,json=body)
    assert saved.status_code==200,saved.text
    assert saved.json()['version']==1 and set(saved.json()['source_bindings'])=={'S','R'}
    assert client.put(base,json=body).status_code==409
    reopened=client.get(base+'?revision=1').json()
    assert reopened['version']==1
    assert reopened['source_bindings']==saved.json()['source_bindings']
    assert reopened['inputs']['ends']['S']['mappings']=={'A1':'ignore'}
    response=client.post(base+'/report',json=dict(revision=1,inputs=inputs(True)))
    assert response.status_code==200,response.text
    assert response.json()['ends']['S']['sample_count']>220
    assert response.json()['ends']['S']['source_sha256']==saved.json()['source_bindings']['S']
    row=app.state.store.get(identity)
    path=Path(row['bundle']['root'])/'S/event.dat'
    path.write_bytes(path.read_bytes()+b'\n')
    response=client.post(base+'/report',json=dict(revision=1,inputs=inputs()))
    assert response.status_code==400,response.text
    assert 'checksum' in response.text.lower()


def test_event_api_revision_and_input_validation(environment):
    client,app,identity=_incident(environment)
    base=f'/api/incidents/{identity}/event-study'
    assert client.get(base+'?revision=99').status_code==404
    assert client.post(base+'/report',json=dict(revision=True,inputs=inputs())).status_code==400
    assert client.post(base+'/report',json=dict(revision=1,inputs=inputs(),unknown=1)).status_code==400
    assert client.put(base,json=dict(revision=1,expected_version=True,inputs=inputs())).status_code==400
    row=app.state.store.get(identity)
    app.state.store.submit(name='new revision',source='test',files=row['files'],metadata={},fingerprint='next-revision',
        incident_id=identity,expected=1)
    assert client.put(base,json=dict(revision=1,expected_version=0,inputs=inputs())).status_code==409
