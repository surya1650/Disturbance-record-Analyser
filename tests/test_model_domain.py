"""Independent section physics and enforced scalar-model domain boundaries."""
import copy

import numpy as np
import pytest

from dranalyser.faultloc.ensemble import TerminalInput,locate
from dranalyser.faultloc.estimators import e4_synchronised,e5_unsynchronised
from dranalyser.faultloc.model_domain import scalar_model_reasons
from dranalyser.faultloc.stage_location import stage_e5
from dranalyser.registry.model import LineSection
from tests.section_network_oracle import negative,solve
from tests.test_stage_location import line,reviewed_pair

MIXED=[(40,.03+.25j,.4+1.4j),(60,.3+.7j,.1+1j)]


def definition(sections):
    result=line()
    result.sections=[]
    start=0
    for i,(length,z1,z0) in enumerate(sections):
        result.sections.append(LineSection(i+1,start,start+length,z1.real,z1.imag,z0.real,z0.imag))
        start+=length
    return result


@pytest.mark.parametrize('km',[1,39.9,40,40.1,75,99])
@pytest.mark.parametrize('phase',[0,1,2])
def test_independent_section_network_kcl_and_terminal_reversal(km,phase):
    state=solve(MIXED,km,phase)
    for j in range(1,len(state['nodes'])-1):
        v=state['voltages']
        currents=state['branches'][j-1][0]@(v[j]-v[j-1])+state['branches'][j][0]@(v[j]-v[j+1])
        injection=np.zeros(3,complex)
        if j==state['fault_node']:
            injection[phase]=v[j,phase]/4
        np.testing.assert_allclose(currents+injection,0,atol=1e-7)
    assert scalar_model_reasons(definition(MIXED))
    reverse=solve(MIXED[::-1],100-km,phase,reverse_sources=True)
    for key,opposite in [('VS','VR'),('IS','IR'),('VR','VS'),('IR','IS')]:
        np.testing.assert_allclose(state[key],reverse[opposite],rtol=1e-9,atol=1e-6)
    # Explicit junctions and local Ohm drops survive reversing the physical line.
    for i,(y,_) in enumerate(state['branches']):
        np.testing.assert_allclose(np.linalg.inv(y)@(y@(state['voltages'][i]-state['voltages'][i+1])),
                                   state['voltages'][i]-state['voltages'][i+1],atol=1e-7)


@pytest.mark.parametrize('km',[10,39.9,40,40.1,90])
def test_proportional_sections_have_independent_uniform_scalar_limit(km):
    sections=[(40,.03+.25j,.1+.75j),(60,.06+.5j,.2+1.5j)]
    d=definition(sections)
    assert not scalar_model_reasons(d)
    state=solve(sections,km)
    quantities=[negative(state[k]) for k in ('VS','IS','VR','IR')]
    expected=(min(km,40)*.25+max(km-40,0)*.5)/40
    for estimator in (e4_synchronised(*quantities,d.z1),e5_unsynchronised(*[[v]*8 for v in quantities],d.z1)):
        assert estimator.ok and estimator.m==pytest.approx(expected,abs=1e-10)
        assert d.m_to_km(estimator.m)==pytest.approx(km,abs=1e-8)
    reversed_e4=e4_synchronised(*quantities[2:],*quantities[:2],d.z1)
    assert reversed_e4.m==pytest.approx(1-expected,abs=1e-10)


def test_wrong_summed_model_does_not_pass_mixed_section_oracle():
    d=definition(MIXED)
    state=solve(MIXED,40)
    estimate=e4_synchronised(*[negative(state[k]) for k in ('VS','IS','VR','IR')],d.z1)
    assert abs(d.m_to_km(estimate.m)-40)>.1
    assert 'Nonproportional' in ' '.join(scalar_model_reasons(d))


@pytest.mark.parametrize('problem',['sections','shunt','double circuit','series compensation','invalid geometry','nonfinite'])
def test_both_entrypoints_refuse_unsupported_declared_models(problem):
    ans,rows=reviewed_pair()
    d=copy.deepcopy(line())
    if problem=='sections':
        d=definition(MIXED)
    elif problem=='shunt':
        d.sections[0].b1=2e-6
    elif problem=='double circuit':
        d.double_circuit=True
    elif problem=='series compensation':
        d.series_compensated=True
    elif problem=='nonfinite':
        d.sections[0].x1=np.nan
    else:
        d.sections[0].from_km=1
    # Use a single settled window so the unrelated stage-transition guard
    # cannot conceal a bypass of model-domain refusal.
    single=copy.deepcopy(ans['S'])
    single.window.t_start,single.window.t_end=rows[0]['stages']['intervals'][0]['estimation_window']['window_s']
    result=locate(d,{'S':TerminalInput(single,'S')})
    assert not result.ok and not result.towers and np.isnan(result.km_from_S)
    assert result.diagnostics['model_domain']=='unsupported'
    result=stage_e5(d,ans['S'],ans['R'],*(r['stages']['intervals'][0] for r in rows))
    assert result['status']=='withheld' and result['m'] is None


def test_pi_charging_changes_terminal_currents_and_requires_a_different_model():
    sections=[(300,.03+.4j,.2+1.2j)]
    plain=solve(sections,110)
    charged=solve(sections,110,charging=4e-6)
    assert np.linalg.norm(charged['IS']-plain['IS']) > 10
    d=definition(sections)
    d.sections[0].b1=4e-6
    assert 'charging' in ' '.join(scalar_model_reasons(d))
