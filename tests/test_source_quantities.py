"""Hand-derived source-phasor composition; no production fitter generates truth."""
import importlib
import math

import pytest


def compose(channels,windows,line_model=None,fault_loop=''):
    module=importlib.import_module('dranalyser.workbench.source_quantities')
    return module.compose_source_quantities(channels,windows,line_model,fault_loop)


def phase_fixture(z=1+4j):
    # Positive ABC sequence: a=exp(j120deg), Ib=10*a², Ic=10*a.
    a=complex(-.5,math.sqrt(3)/2)
    current={'A':10+0j,'B':10*a*a,'C':10*a}
    channels=[]
    fits={}
    for quantity,phasors,unit in [('V',{p:value*z for p,value in current.items()},'V'),('I',current,'A')]:
        for phase in ('A','B','C'):
            key=f'A{len(channels)+1}'
            value=phasors[phase]
            channels.append(dict(id=key,meaning=quantity+phase,label=quantity+phase,units=unit))
            fits[key]=dict(status='model_consistent',phasor=[value.real,value.imag],centre_s=.04)
    return channels,[dict(index=0,support_s=[0,.08],coverage_status='covered',frequency={'status':'estimated','frequency_hz':50},channels=fits)]


def test_balanced_sequences_and_phase_loops_match_hand_phasors():
    channels,windows=phase_fixture()
    out=compose(channels,windows)
    w=out['windows'][0]
    assert complex(*w['sequence']['current']['positive'])==pytest.approx(10+0j,abs=1e-12)
    assert complex(*w['sequence']['voltage']['positive'])==pytest.approx(10+40j,abs=1e-12)
    assert complex(*w['sequence']['current']['zero'])==pytest.approx(0j,abs=1e-12)
    assert complex(*w['sequence']['current']['negative'])==pytest.approx(0j,abs=1e-12)
    for loop in ('AB','BC','CA'):
        assert complex(*w['loops'][loop]['impedance_ohm'])==pytest.approx(1+4j)
        assert w['loops'][loop]['units']=='ohm (conditional source scaling)'
    assert out['authorizes_location'] is out['alignment_eligible'] is False
    assert w['projection']['status']=='Not available'


def test_unbalanced_components_are_not_forced_to_zero():
    channels,windows=phase_fixture()
    for i in range(1,7):
        windows[0]['channels'][f'A{i}']['phasor']=[30 if i==1 else 3 if i==4 else 0,0]
    out=compose(channels,windows)['windows'][0]
    for component in ('zero','positive','negative'):
        assert complex(*out['sequence']['voltage'][component])==pytest.approx(10+0j)
        assert complex(*out['sequence']['current'][component])==pytest.approx(1+0j)


def test_homogeneous_model_projection_is_labelled_conditional_and_has_residual():
    channels,windows=phase_fixture()
    line={'length_km':50,'x1_ohm_per_km':.4,'r1_ohm_per_km':.1,'provenance':'explicit test model'}
    out=compose(channels,windows,line,'AB')['windows'][0]['projection']
    assert out['status']=='Conditional model projection'
    assert out['distance_km']==pytest.approx(10)
    assert out['fraction']==pytest.approx(.2)
    assert out['residual']==pytest.approx(0,abs=1e-12)
    assert out['method'] and out['assumptions'] and out['eligible_overlay']
    assert out['authorizes_location'] is False


def test_piecewise_reactance_projection_retains_correct_section():
    channels,windows=phase_fixture(2+8j)
    line={'length_km':20,'sections':[{'from_km':0,'to_km':10,'x1_ohm_per_km':.4,'r1_ohm_per_km':.1},
        {'from_km':10,'to_km':20,'x1_ohm_per_km':.8,'r1_ohm_per_km':.2}],'provenance':'explicit sections'}
    p=compose(channels,windows,line,'BC')['windows'][0]['projection']
    assert p['distance_km']==pytest.approx(15)
    assert p['fraction']==pytest.approx(.75)
    assert p['section_index']==1
    assert p['residual']==pytest.approx(0,abs=1e-12)


@pytest.mark.parametrize('case',['missing','duplicate','ignored','counts','wrong_units','withheld','centre','missing_centre','nonfinite','nonfinite_frequency','cancel'])
def test_missing_or_incompatible_prerequisites_do_not_invent_rx(case):
    channels,windows=phase_fixture()
    if case=='missing':
        channels=channels[1:]
    if case=='duplicate':
        channels.append(dict(channels[0],id='A7'))
    if case=='ignored':
        channels[0]['meaning']='ignore'
    if case=='counts':
        channels[0]['units']='raw counts'
    if case=='wrong_units':
        channels[0]['units']='A'
    if case=='withheld':
        windows[0]['channels']['A1']={'status':'withheld','reason':'missing support'}
    if case=='centre':
        windows[0]['channels']['A1']['centre_s']=.041
    if case=='missing_centre':
        windows[0]['channels']['A1'].pop('centre_s')
    if case=='nonfinite':
        windows[0]['channels']['A1']['phasor']=[float('nan'),1]
    if case=='nonfinite_frequency':
        windows[0]['frequency']['frequency_hz']=float('nan')
    if case=='cancel':
        windows[0]['channels']['A5']['phasor']=[10*(1-1e-12),0]
    w=compose(channels,windows)['windows'][0]
    assert w['loops']['AB']['status']=='Not available'
    assert w['loops']['AB']['reason'] and w['loops']['AB']['impedance_ohm'] is None


def test_unavailable_current_sequence_does_not_erase_voltage_or_ab_loop():
    channels,windows=phase_fixture()
    channels=[c for c in channels if c['meaning']!='IC']
    w=compose(channels,windows)['windows'][0]
    assert w['sequence']['current']['status']=='Not available'
    assert w['sequence']['voltage']['status']=='Conditional source quantity'
    assert w['loops']['AB']['status']=='Conditional source quantity'


@pytest.mark.parametrize('line',[{}, {'length_km':0,'x1_ohm_per_km':.4}, {'length_km':50,'x1_ohm_per_km':0},
    {'length_km':50,'x1_ohm_per_km':float('nan')}, {'length_km':True,'x1_ohm_per_km':.4}])
def test_missing_or_invalid_line_never_yields_fake_distance(line):
    channels,windows=phase_fixture()
    p=compose(channels,windows,line,'AB')['windows'][0]['projection']
    assert p['status']=='Not available' and p['distance_km'] is None and p['reason']


@pytest.mark.parametrize('z,expected',[(1-4j,-10),(1+40j,100)])
def test_out_of_line_projection_is_explicit_and_not_clipped(z,expected):
    channels,windows=phase_fixture(z)
    p=compose(channels,windows,{'length_km':50,'x1_ohm_per_km':.4},'AB')['windows'][0]['projection']
    assert p['status']=='Outside supplied line'
    assert p['distance_km']==pytest.approx(expected)
    assert not p['eligible_overlay'] and not p['authorizes_location']


def test_ground_loop_or_unspecified_fault_loop_cannot_be_guessed():
    channels,windows=phase_fixture()
    for loop in ('','AG'):
        p=compose(channels,windows,{'length_km':50,'x1_ohm_per_km':.4},loop)['windows'][0]['projection']
        assert p['status']=='Not available' and p['distance_km'] is None
