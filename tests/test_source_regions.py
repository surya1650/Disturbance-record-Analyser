"""Automatic display intervals stay bounded by observed source support."""
import copy
import math

import pytest

from dranalyser.workbench.source_regions import auto_regions
from dranalyser.synth.generator import SynthSpec, TerminalSpec, generate


def capture(*,fault=True,ongoing=False,second=False):
    times=[i/1000 for i in range(500)]
    channels=[]
    for j,meaning in enumerate(('Va','v_b','V-C','Ia','i_b','I-C')):
        values=[]
        for i,t in enumerate(times):
            active=fault and (120<=i<(500 if ongoing else 240) or second and 380<=i<440)
            magnitude=(50 if active else 100) if j<3 else (5 if active else 1 if i<120 else 0)
            values.append(magnitude*math.sqrt(2)*math.sin(2*math.pi*50*t+j))
        channels.append(dict(key='A'+str(j+1),label=meaning,units='V' if j<3 else 'A',values=values))
    return dict(sample_count=len(times),axis={'elapsed_s':times},channels=channels,digital=[],
                nominal_frequency_hz=50,header_inventory=[])


def test_detects_three_regions_without_manual_indices_or_trigger():
    source=capture()
    before=copy.deepcopy(source)
    result=auto_regions(source,{})
    assert result['status']=='selected'
    assert result['pre'][1]<=120 and result['fault'][0]>=120
    assert result['fault'][1]<=240 and result['post'][0]>=240
    for name in ('pre','fault','post'):
        lo,hi=result[name]
        assert 0<=lo<hi<=source['sample_count']
        assert source['axis']['elapsed_s'][hi-1]-source['axis']['elapsed_s'][lo]>=.02
    for name,actual in [('start',.12),('end',.24)]:
        lo,hi=result['boundaries'][name]['support_s']
        assert lo-.001<=actual<=hi+.001
    assert result['authorizes_location'] is False
    assert result['timeline']['trigger_offset_s'] is None
    assert source['channels']==before['channels'] and source['axis']==before['axis']
    assert result['intervals']['fault']['start_s']==source['axis']['elapsed_s'][result['fault'][0]]


@pytest.mark.parametrize('fs,fault,m,rf',[(1000,'AG',.1,1),(1200,'AB',.5,5),(2400,'ABC',.9,10)])
def test_synthetic_generator_oracle_across_rates_types_distances(fs,fault,m,rf):
    spec=SynthSpec(m=m,fault=fault,rf=rf,S=TerminalSpec(fs=fs,prefault_s=.12,post_s=.3,
        noise_pct=0,adc_bits=20,cvt_transient=False,trip_delay_s=.02,breaker_time_s=.08))
    rec=generate(spec).records['S']
    names=('VA','VB','VC','IA','IB','IC')
    source=dict(sample_count=rec.n,axis={'elapsed_s':(rec.t-rec.t[0]).tolist()},
        channels=[dict(key='A'+str(i+1),label=name,units='V' if name.startswith('V') else 'A',values=rec.analog[name].tolist()) for i,name in enumerate(names)],
        digital=[],nominal_frequency_hz=50,header_inventory=[])
    result=auto_regions(source,{})
    assert result['fault'] is not None,result
    onset=spec.S.prefault_s-float(rec.t[0])
    lo,hi=result['boundaries']['start']['support_s']
    assert lo-1/fs<=onset<=hi+1/fs
    assert not result['authorizes_location']


def test_steady_ongoing_second_event_and_missing_support_are_explicit():
    assert auto_regions(capture(fault=False),{})['fault'] is None
    ongoing=auto_regions(capture(ongoing=True),{})
    assert ongoing['fault'] and ongoing['post'] is None
    assert 'capture boundary' in ' '.join(ongoing['notes'])
    second=auto_regions(capture(second=True),{})
    assert second['post'][1]<380 and 'later changed pattern' in ' '.join(second['notes'])
    missing=capture()
    for c in missing['channels']:
        c['values'][180]=None
    gap=auto_regions(missing,{})
    assert gap['post'] is None and gap['fault'][1]<=180
    assert 'Missing RMS support' in ' '.join(gap['notes'])


def test_short_and_untimed_captures_do_not_invent_an_event():
    source=capture()
    source['axis']['elapsed_s']=[]
    assert auto_regions(source,{})['status']=='unavailable'
    short=capture()
    short['sample_count']=15
    short['axis']['elapsed_s']=short['axis']['elapsed_s'][:15]
    for c in short['channels']:
        c['values']=c['values'][:15]
    assert auto_regions(short,{})['fault'] is None


def test_trigger_inside_initial_baseline_prevents_false_healthy_prefault():
    source=capture()
    source['recorded_times']=dict(start='01/01/2026,00:00:00.000000',trigger='01/01/2026,00:00:00.012000')
    result=auto_regions(source,{})
    assert result['pre'] is None and result['fault'] is not None
    assert 'healthy pre-fault interval is not established' in ' '.join(result['notes'])


def test_short_prefault_start_indication_retains_its_observed_basis():
    source=capture(fault=False)
    source['digital']=[dict(key='D1',label='START',states=[0]*12+[1]*488)]
    source['header_inventory']=[dict(id='D1',normal_state='0')]
    result=auto_regions(source,{})
    assert result['status']=='partial' and result['pre'] is None and result['fault']==[12,72]
    assert result['post'] is None and 'Recorded START' in result['method']
    unknown=capture(fault=False)
    unknown['digital']=source['digital']
    assert auto_regions(unknown,{})['fault'] is None


def test_choices_cache_is_bounded_copied_and_separates_polarity():
    source=capture(fault=False)
    a=auto_regions(source,{})
    a['notes'].append('external edit')
    assert 'external edit' not in auto_regions(source,{})['notes']
    for i in range(8):
        auto_regions(source,{'channel_mapping':{'analog':{},'reason':str(i)}})
    assert len(source['_auto_regions'])==4
