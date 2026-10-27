"""Source analysis stays useful with explicit assumptions and method-specific reasons."""
import hashlib
import importlib

import pytest

from tests import test_source_inspection as source_fixtures

revision=source_fixtures.revision


def api(name):
    return getattr(importlib.import_module('dranalyser.workbench.source_diagnostics'),name)


def update(revision, transform):
    root,row,folder=revision
    cfg=folder/'event.cfg'
    cfg.write_text(transform(cfg.read_text()))
    for item in row['files']:
        item['sha256']=hashlib.sha256((folder/item['name']).read_bytes()).hexdigest()
    return root,row


@pytest.mark.parametrize('kv,ratio',[(132,600),(220,800)])
def test_user_default_only_fills_missing_secondary_current_ratio(revision,kv,ratio):
    root,row=update(revision,lambda s:s.replace('32767,1,1,P','32767,,,S',1))
    out=api('diagnose_source')(root,row,'event.cfg',{'voltage_kv':kv})
    a=out['channels'][0]
    assert a['sample_min']==21*ratio and a['sample_max']==27*ratio
    assert out['assumptions'][0]['ratio']==ratio
    assert out['assumptions'][0]['source']=='user voltage-level default'
    assert out['ct_vt_verified'] is out['authorizes_location'] is False
    assert out['source_sha256'] and out['options']['voltage_kv']==kv


def test_valid_declared_ratio_is_never_overwritten(revision):
    root,row=update(revision,lambda s:s.replace('32767,1,1,P','32767,100,1,S',1))
    out=api('diagnose_source')(root,row,'event.cfg',{'voltage_kv':220})
    assert out['channels'][0]['sample_min']==2100
    assert out['assumptions']==[]


@pytest.mark.parametrize('field,value',[(5,''),(4,''),(12,''),(12,'P')])
def test_ratio_default_cannot_invent_missing_gain_unit_or_side(revision,field,value):
    def alter(s):
        lines=s.splitlines()
        f=lines[2].split(',')
        f[10:13]=['','','S']
        f[field]=value
        lines[2]=','.join(f)
        return '\n'.join(lines)+'\n'
    root,row=update(revision,alter)
    out=api('diagnose_source')(root,row,'event.cfg',{'voltage_kv':132})
    assert not out['assumptions']
    assert all(c['sample_min'] is None or isinstance(c['sample_min'],(int,float)) for c in out['channels'])
    assert out['methods']['location']['status']=='Not available'


def test_trip_unknown_state_and_explicit_ignore_are_preserved(revision):
    root,row,_=revision
    out=api('diagnose_source')(root,row,'event.cfg',{'mappings':{'D1':'TRIP'}})
    d=out['digital_evidence'][0]
    assert d['id']=='D1' and d['unknown_samples']==1 and d['first_active_index']==1
    assert d['rising_edges'][0]['sample_bracket']==[0,1]
    assert d['rising_edges'][0]['source_bracket_s']==pytest.approx([0,.0008])
    assert out['trip']['status']=='Observed indication'
    ignored=api('diagnose_source')(root,row,'event.cfg',{'mappings':{'D1':'ignore'}})
    assert ignored['trip']['status']=='Not available'
    assert ignored['digital_evidence'][0]['meanings']==[]
    assert ignored['conclusions']['observed'] and ignored['conclusions']['cannot_conclude']


def test_ar_block_is_possible_explanation_with_linked_recorded_evidence(revision):
    root,row,_=revision
    out=api('diagnose_source')(root,row,'event.cfg',{'mappings':{'D1':'AR_BLOCK'}})
    assert out['ar']['status']=='Possible explanation'
    assert out['ar']['evidence_ids']==['D1']
    assert 'inhibit' in out['ar']['text'].lower()
    assert 'Not available'==out['methods']['rx']['status']


@pytest.mark.parametrize('options',[{'voltage_kv':True},{'voltage_kv':33},{'mappings':{'A99':'IA'}},
    {'mappings':{'D1':'IA'}},{'mappings':{'A1':'IA','A2':'IA'}},{'extra':1}])
def test_bad_options_and_ambiguous_explicit_meanings_refuse_locally(revision,options):
    root,row,_=revision
    with pytest.raises(ValueError):
        api('diagnose_source')(root,row,'event.cfg',options)


def test_digital_edge_evidence_has_a_global_response_bound():
    from dranalyser.workbench.source_events import digital_evidence
    source={'axis':{'elapsed_s':[]},'digital':[{'key':f'D{i+1}','label':'unmapped','states':[0,1]*50} for i in range(100)]}
    rows=digital_evidence(source,{})
    assert sum(len(c['rising_edges'])+len(c['falling_edges']) for c in rows)<=4096
    assert sum(c['omitted_edges'] for c in rows)>0
    assert all(c['active_samples']==50 and c['unknown_samples']==0 for c in rows)
