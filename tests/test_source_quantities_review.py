"""Single review-fix pass: unknown close outcomes and numeric projection safety."""
import json

import pytest

from dranalyser.workbench.source_events import digital_evidence,trip_ar
from dranalyser.workbench.source_quantities import compose_source_quantities


def close_evidence(*,normal='1',states=None,block=False,include_close=True):
    source={'axis':{'elapsed_s':[0,.001,.002]},
        'header_inventory':[{'id':'D1','normal_state':'0'},{'id':'D2','normal_state':normal},{'id':'D3','normal_state':'0'}],
        'digital':[{'key':'D1','label':'init','states':[0,1,1]}]}
    meanings={'D1':'AR_INITIATE'}
    if include_close:
        source['digital'].append({'key':'D2','label':'close','states':states if states is not None else [1,1,0]})
        meanings['D2']='AR_CLOSE'
    if block:
        source['digital'].append({'key':'D3','label':'block','states':[0,1,1]})
        meanings['D3']='AR_BLOCK'
    return digital_evidence(source,meanings)


def test_unknown_close_polarity_is_not_a_no_close_explanation():
    ar=trip_ar(close_evidence())[1]
    assert ar['status']=='Not available'
    assert 'polarity' in ar['text'].lower() and 'D2' in ar['text']
    assert 'no assigned close assertion observed' not in ar['text'].lower()


def test_independent_supported_cause_retains_unknown_polarity_warning():
    ar=trip_ar(close_evidence(block=True))[1]
    assert ar['status']=='Possible explanation' and 'inhibit' in ar['text'].lower()
    assert 'polarity' in ar['text'].lower() and 'D2' in ar['text']
    assert 'no assigned close assertion observed' not in ar['text'].lower()


@pytest.mark.parametrize('case',['missing_states','missing_channel'])
def test_missing_close_observations_are_unknown_not_zero(case):
    rows=close_evidence(normal='0',states=[0,None,0],include_close=case!='missing_channel')
    ar=trip_ar(rows)[1]
    assert ar['status']=='Not available'
    assert 'unknown' in ar['text'].lower() or 'unavailable' in ar['text'].lower()
    assert 'no assigned close assertion observed' not in ar['text'].lower()


def test_known_sampled_close_absence_remains_a_possible_capture_explanation():
    ar=trip_ar(close_evidence(normal='0',states=[0,0,0]))[1]
    assert ar['status']=='Possible explanation'
    assert 'no assigned close assertion observed' in ar['text'].lower()


def simple_projection(voltage,current,line):
    channels=[{'id':'A1','meaning':'VA','units':'V'},{'id':'A2','meaning':'VB','units':'V'},
        {'id':'A3','meaning':'IA','units':'A'},{'id':'A4','meaning':'IB','units':'A'}]
    fits={key:dict(status='model_consistent',phasor=value,centre_s=.04) for key,value in
        [('A1',voltage),('A2',[0,0]),('A3',current),('A4',[0,0])]}
    window=dict(index=0,support_s=[0,.08],coverage_status='covered',frequency={'status':'estimated','frequency_hz':50},channels=fits)
    result=compose_source_quantities(channels,[window],line,'AB')
    json.dumps(result,allow_nan=False)
    return result['windows'][0]


def test_nonzero_reactance_underflow_never_becomes_a_zero_km_marker():
    row=simple_projection([1,1e-20],[1,0],{'length_km':1,'x1_ohm_per_km':1e308})
    assert row['loops']['AB']['impedance_ohm']==[1,1e-20]
    p=row['projection']
    assert p['status']=='Not available' and p['distance_km'] is None
    assert not p['eligible_overlay'] and 'underflow' in p['reason'].lower()


def test_nonzero_fraction_underflow_cannot_draw_at_the_terminal():
    p=simple_projection([1,1e-200],[1,0],{'length_km':1e308,'x1_ohm_per_km':1})['projection']
    assert p['status']=='Not available' and p['fraction'] is None
    assert not p['eligible_overlay']


def test_finite_large_complex_values_do_not_abort_other_quantities():
    row=simple_projection([1.7e208,1.7e208],[1e-100,0],
        {'length_km':1,'x1_ohm_per_km':1.7e308,'r1_ohm_per_km':1.7e308})
    p=row['projection']
    assert p['status']=='Conditional model projection' and p['distance_km']==pytest.approx(1)
    assert p['residual']==pytest.approx(0,abs=1e-14)
    assert not p['authorizes_location']
    assert row['loops']['AB']['status']=='Conditional source quantity'
