"""Independent network truth, guarded E5 and source-review enforcement."""
import copy

import numpy as np
import pytest

from dranalyser.dsp.pipeline import analyse
from dranalyser.dsp.stage_windows import stage_window
from dranalyser.dsp.window_quality import window_transition
from dranalyser.faultloc.ensemble import TerminalInput, locate
from dranalyser.faultloc.stage_location import stage_e5
from dranalyser.faultloc.estimators import Estimate
from dranalyser.registry.model import uniform_line
from dranalyser.report.evidence import render_evidence
from dranalyser.rules.evidence import relay_evidence
from dranalyser.workbench.stage_location import stage_locations
from dranalyser.workbench.stage_review import apply_stage_review, clean_stage_review
from tests.staged_network_oracle import ES, ER, LINE, SOURCE_S, SOURCE_R, network, scenario


def line():
    return uniform_line('SYNTHETIC-NETWORK', 'Independent synthetic network', 220, 100,
                        .09+.30j, .24+.66j, 3+12j, 6+21j, 5+18j, 11+33j)


def reviewed_pair(fs=1200, pre=.173, stage2_m=.32):
    analyses, rows = {}, []
    for end in ('S', 'R'):
        rec, _ = scenario(end=end, fs=2400 if end == 'S' else fs,
                          pre=.12 if end == 'S' else pre, clock=0 if end == 'S' else 1418,
                          stage2_m=stage2_m)
        an = analyses[end] = analyse(rec)
        row = relay_evidence(an, end+'.cfg', end, protection_system='Main-1')
        apply_stage_review(row, line_id=line().id, incident_id='synthetic')
        active = [s for s in row['stages']['intervals'] if s['stable'] and s['phase_pattern']]
        review = dict(inventory_hash=row['stages']['inventory_hash'], reviewer='Synthetic network reviewer',
                      reason='Independent branch-equation schedule; synthetic only',
                      groups={s['id']: str(i) for i, s in enumerate(active)},
                      same_incident=True, same_circuit=True, stage_identity=True, location_requested=True)
        apply_stage_review(row, review, line().id, 'synthetic')
        rows.append(row)
    return analyses, rows


@pytest.mark.parametrize('m,phases', [(.1, 'A'), (.32, 'AB'), (.5, 'BC'), (.73, 'A'), (.9, 'ABC')])
def test_independent_branch_network_satisfies_source_ohm_laws_and_fault_kcl(m, phases):
    s = network(m, phases)
    np.testing.assert_allclose(s['VS']+SOURCE_S@s['IS'], ES, atol=1e-7)
    np.testing.assert_allclose(s['VR']+SOURCE_R@s['IR'], ER, atol=1e-7)
    np.testing.assert_allclose(s['VS']-s['VF'], m*LINE@s['IS'], atol=1e-7)
    np.testing.assert_allclose(s['VR']-s['VF'], (1-m)*LINE@s['IR'], atol=1e-7)
    np.testing.assert_allclose(s['IS']+s['IR'], [s['VF'][i]/5 if p in phases else 0 for i,p in enumerate('ABC')], atol=1e-7)


@pytest.mark.parametrize('fs,pre,m2', [(1000,.17,.32), (1200,.173,.32), (2400,.157,.61)])
def test_separate_stage_estimates_match_network_truth_without_clock_alignment(fs, pre, m2):
    ans, rows = reviewed_pair(fs, pre, m2)
    before = {e: (copy.deepcopy(a.window), {k:v.copy() for k,v in a.record.analog.items()}) for e,a in ans.items()}
    results = stage_locations(line(), ans, rows, {'S':'S.cfg','R':'R.cfg'})
    assert len(results) == 3
    for result, expected in zip(results, (.32,m2,.73), strict=True):
        assert result['status'] == 'located', result
        assert result['m'] == pytest.approx(expected, abs=1e-8)
        assert result['km_from_S'] == pytest.approx(100*expected, abs=1e-6)
        assert result['method'] == 'E5' and not result['clock_shift_applied']
        assert all(w['whole_record_saturation'] and not w['local_saturation'] for w in result['windows'].values())
        for end,w in result['windows'].items():
            an=ans[end]
            ids=an.ps.window_indices(*w['window_s'])
            support=an.ps.t[ids]-(an.ps.n_window-1)/an.ps.fs
            assert np.min(support) >= w['window_s'][0]-1e-12
            assert np.max(an.ps.t[ids]) <= w['window_s'][1]
    for end,an in ans.items():
        assert an.window == before[end][0]
        for k,v in before[end][1].items():
            np.testing.assert_array_equal(an.record.analog[k],v)
    html=render_evidence(rows, [], stage_locations=results)
    assert 'Reviewed stage locations' in html and '73.000 km' in html


def test_mixed_legacy_window_refuses_before_any_estimator(monkeypatch):
    ans, _ = reviewed_pair(stage2_m=.61)
    assert all(window_transition(a)['status'] == 'transition detected' for a in ans.values())
    def forbidden(*args):
        pytest.fail('Mixed states reached the legacy median estimator')
    monkeypatch.setattr('dranalyser.faultloc.ensemble._single_ended', forbidden)
    result=locate(line(), {e:TerminalInput(a, e) for e,a in ans.items()})
    assert result.method == 'none' and np.isnan(result.m)
    assert 'window_gates' in result.diagnostics


@pytest.mark.parametrize('problem', ['no opt in','one opt in','stale','different group','missing remote','corroborating only','no line'])
def test_review_and_selected_terminal_prerequisites_cannot_be_inferred(problem):
    ans, rows=reviewed_pair()
    used={'S':'S.cfg','R':'R.cfg'}
    definition=line()
    if problem in ('no opt in','one opt in'):
        for row in rows[:2 if problem=='no opt in' else 1]:
            row['stages']['review'].pop('location_requested')
    elif problem=='stale':
        rows[0]['record_hash']='f'*64
        apply_stage_review(rows[0], rows[0]['stages']['review'],line().id,'synthetic')
    elif problem=='different group':
        rows[1]['stages']['reviewed_groups']={k:'other'+v for k,v in rows[1]['stages']['reviewed_groups'].items()}
    elif problem=='missing remote':
        ans.pop('R')
        used.pop('R')
    elif problem=='corroborating only':
        rows[1]['file']='corroborating.cfg'
        used.pop('R')
        ans.pop('R')
    else:
        definition=None
    results=stage_locations(definition,ans,rows,used)
    assert results and all(s['status']=='withheld' and s['m'] is None for s in results)


@pytest.mark.parametrize('problem', ['short','nonfinite','nonstationary','weak sequence','ambiguous roots','series capacitor'])
def test_local_quality_and_solver_refusals(problem, monkeypatch):
    ans,rows=reviewed_pair()
    stages=[r['stages']['intervals'][0] for r in rows]
    definition=line()
    if problem=='short':
        stages[0]['end_s']=stages[0]['start_s']+.025
    elif problem=='nonfinite':
        lo, hi=stage_window(ans['S'],stages[0])['sample_bounds']
        ans['S'].record.analog['IA'][(lo+hi)//2]=np.nan
    elif problem=='nonstationary':
        ids=ans['S'].ps.window_indices(*stage_window(ans['S'],stages[0])['window_s'])
        ans['S'].ps.phasors['VA'][ids]*=np.linspace(1,1.5,len(ids))
    elif problem=='weak sequence':
        ans['S'].ps.phasors['I2'][:]=0
    elif problem=='ambiguous roots':
        monkeypatch.setattr('dranalyser.faultloc.stage_location.e5_roots',lambda *args:([.2,.7],None,None))
    else:
        definition.series_compensated=True
    result=stage_e5(definition,ans['S'],ans['R'],*stages)
    assert result['status']=='withheld' and result['m'] is None, result


def test_location_opt_in_requires_boolean():
    _,rows=reviewed_pair()
    review=rows[0]['stages']['review']
    review['location_requested']='true'
    with pytest.raises(ValueError,match='boolean'):
        clean_stage_review(review)


@pytest.mark.parametrize('m,residual,spread', [(-.1,0,0),(1.1,0,0),(.32,np.nan,0),(.32,0,np.nan),(.32,.1,0),(.32,0,10)])
def test_outside_line_and_untrustworthy_solver_diagnostics_are_withheld(m,residual,spread,monkeypatch):
    ans,rows=reviewed_pair()
    monkeypatch.setattr('dranalyser.faultloc.stage_location.e5_unsynchronised',lambda *args:
                        Estimate('E5',m,residual,diagnostics={'delta_std_deg':spread}))
    result=stage_e5(line(),ans['S'],ans['R'],*(r['stages']['intervals'][0] for r in rows))
    assert result['status']=='withheld' and result['m'] is None and result['km_from_S'] is None
