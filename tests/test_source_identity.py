"""Notation variants retain source identity and cannot merge ambiguous phases."""
import copy

import pytest

from dranalyser.comtrade.source_identity import source_meanings
from dranalyser.workbench.source_diagnostics import _prepared


@pytest.mark.parametrize('label,unit,target', [('Ia','A','IA'),('i_a','A','IA'),('I-A','A','IA'),
    ('i a','A','IA'),('I.a','A','IA'),('I_L1','A','IA'),('i_l2','A','IB'),
    ('Ua','V','VA'),('u_b','V','VB'),('U-L3','V','VC'),('i_n','A','IN'),('LINE1_A_IL1','A','IA')])
def test_case_separator_and_vendor_tail_variants(label,unit,target):
    source=dict(channels=[dict(key='A7',label=label,units=unit,values=[1,2])],header_inventory=[])
    before=copy.deepcopy(source)
    assert source_meanings(source)=={'A7':target}
    prepared,*_= _prepared(source,{},dict(voltage_kv=0,mappings={}))
    assert prepared['channels'][0]['meaning']==target
    assert prepared['channels'][0]['label']==label and prepared['channels'][0]['key']=='A7'
    assert source==before


@pytest.mark.parametrize('label', ['3I0','I0','3V0','VAB','Ia RMS','IARMS','SRC 1 Ia Mag','IA+IB','IN (3I0)','DC IA','IADC','DCIA'])
def test_residual_derived_and_compound_labels_do_not_become_phase_waveforms(label):
    assert source_meanings(dict(channels=[dict(key='A1',label=label,units='A')],header_inventory=[]))=={}


def test_header_conflicts_mixed_conventions_duplicates_and_reviewed_ignore():
    source=dict(channels=[dict(key='A1',label='Ia',units='A',values=[1]),dict(key='A2',label='IA',units='A',values=[2])],header_inventory=[])
    assert source_meanings(source)=={'A1':'IA','A2':'IA'}
    prepared,*_=_prepared(source,{},dict(voltage_kv=0,mappings={'A1':'ignore'}))
    assert [c['meaning'] for c in prepared['channels']]==['ignore','IA']
    source['header_inventory']=[dict(id='A1',phase='B',declared_units='A')]
    assert 'A1' not in source_meanings(source)
    mixed=dict(channels=[dict(key=str(i),label=label,units='A') for i,label in enumerate(['IR','IY','IB','IA','IC'])])
    assert source_meanings(mixed)=={}
    ryb=dict(channels=[dict(key=str(i),label=label,units='A') for i,label in enumerate(['i_r','I-Y','i b'])])
    assert list(source_meanings(ryb).values())==['IA','IB','IC']


def test_legacy_automatic_prefix_does_not_relabel_residual_as_phase_current():
    source=dict(channels=[dict(key='A1',label='3I0',units='A',values=[1])],header_inventory=[])
    item={'channel_inventory':[dict(id='A1',selected='IC',automatic='IC',reviewed=False)]}
    prepared,*_=_prepared(source,item,dict(voltage_kv=0,mappings={}))
    assert prepared['channels'][0]['meaning']==''
    explicit,*_=_prepared(source,item,dict(voltage_kv=0,mappings={'A1':'IN'}))
    assert explicit['channels'][0]['meaning']=='IN'
