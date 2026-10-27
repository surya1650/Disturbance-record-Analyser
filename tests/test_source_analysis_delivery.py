import importlib
import json
import re
import subprocess
import sys

import numpy as np

from tests.test_nonuniform_source import api,source_fixture


def analysis(tmp_path):
    p=source_fixture(tmp_path)
    return api('dsp.source_analysis','analyse_source')(api('comtrade.source_observations','load_source')(p))


def test_one_record_is_reportable_without_line_or_clock(tmp_path):
    out=api('dsp.source_compare','compare_sources')([analysis(tmp_path)])
    assert len(out['records'])==1 and out['distinct_payloads']==1
    assert not out['alignment_eligible'] and not out['authorizes_location']
    assert out['pairing_verified'] is False


def test_local_digital_references_do_not_assert_shared_clock_or_event(tmp_path):
    a=analysis(tmp_path)
    b=json.loads(json.dumps(a))
    b['content_hash']='different'
    n=a['sample_count']
    a['digital']=[dict(key='D1',label='Start',states=[0]*10+[1]*5+[0]*(n-15))]
    b['digital']=[dict(key='D1',label='Start',states=[0]*20+[1]*5+[0]*(n-25))]
    out=api('dsp.source_compare','compare_sources')([a,b],reference='Start')
    assert [r['local_reference']['sample_index'] for r in out['records']]==[10,20]
    assert out['alignment_eligible'] is out['pairing_verified'] is False
    assert out['records'][0]['digital_intervals'][0]['source_span_s']>0


def test_identical_payloads_are_duplicates_not_corroboration(tmp_path):
    a=analysis(tmp_path)
    out=api('dsp.source_compare','compare_sources')([a,a])
    assert out['distinct_payloads']==1
    assert out['records'][1]['duplicate_of']==0


def test_initially_high_or_missing_digital_does_not_invent_reference(tmp_path):
    a=analysis(tmp_path)
    a['digital']=[dict(key='D1',label='Start',states=[1]*a['sample_count'])]
    out=api('dsp.source_compare','compare_sources')([a],reference='Start')
    assert out['records'][0]['local_reference']['status']=='unavailable'
    assert out['records'][0]['digital_intervals'][0]['source_span_s'] is None


def test_report_escapes_untrusted_labels_and_contains_partial_analysis(tmp_path):
    a=analysis(tmp_path)
    a['station']='<script>alert(1)</script>'
    out=api('dsp.source_compare','compare_sources')([a])
    html=api('report.source_analysis','render_source_report')(out)
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
    assert 'CFG-declared' in html and 'sample' in html.lower()
    assert 'Physical timing' in html


def test_cli_publishes_partial_report_exclusively_without_source_writes(tmp_path):
    p=source_fixture(tmp_path/'source')
    before={q:q.read_bytes() for q in (p,p.with_suffix('.dat'))}
    target=tmp_path/'published'
    command=[sys.executable,'scripts/analyse_source_record.py','--cfg',str(p),'--output',str(target)]
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    data=json.loads((target/'analysis.json').read_text())
    assert len(data['records'])==1 and (target/'index.html').exists()
    assert subprocess.run(command,capture_output=True).returncode!=0
    assert all(q.read_bytes()==b for q,b in before.items())


def test_a_neutral_zero_channel_cannot_poison_phase_frequency_references(tmp_path):
    p=source_fixture(tmp_path)
    obs=api('comtrade.source_observations','load_source')(p)
    obs['channels'].append(dict(key='A7',label='VN',units='V (CFG-declared, unverified)',
        values=[0]*obs['sample_count'],frequency_reference=False,skew_us=0))
    out=api('dsp.source_analysis','analyse_source')(obs)
    assert out['windows'][0]['channels']['A1']['status']=='model_consistent'
    assert out['windows'][0]['channels']['A7']['status']=='withheld'


def test_loader_excludes_declared_neutral_from_frequency_reference(tmp_path):
    p=source_fixture(tmp_path)
    p.write_text(p.read_text().replace('1,VA,A,,V','1,VN,N,,V'))
    obs=api('comtrade.source_observations','load_source')(p)
    assert not obs['channels'][0]['frequency_reference']


def test_many_digital_channels_with_bounded_cells_parse(tmp_path):
    p=source_fixture(tmp_path,n=96)
    lines=p.read_text().splitlines()
    lines[1]='82,6A,76D'
    lines[8:8]=[f'{i},D{i},,,0' for i in range(1,77)]
    p.write_text('\n'.join(lines)+'\n')
    dat=p.with_suffix('.dat')
    dat.write_text('\n'.join(row+76*',0' for row in dat.read_text().splitlines())+'\n')
    obs=api('comtrade.source_observations','load_source')(p)
    assert obs['sample_count']==96 and len(obs['digital'])==76


def test_independent_grid_preserves_failures_and_denominator(monkeypatch):
    runner=importlib.import_module('scripts.nonuniform_validation')
    def fail(_):
        raise AssertionError('deliberate oracle failure')
    monkeypatch.setattr(runner,'evaluate',fail)
    out=runner.run(grid=runner.case_grid()[:2])
    assert out['planned']==out['failed']==2 and len(out['cases'])==2
    assert out['study_gate']=='failed'
    json.dumps(out,allow_nan=False)


def test_direct_model_does_not_certify_coherent_gain_error():
    t=np.arange(97)/1200
    y=120*np.sqrt(2)*np.cos(2*np.pi*50*t)
    out=api('dsp.nonuniform','fit_source_window')(t,y,50)
    assert out['status']=='model_consistent' and abs(out['rms']-100)>19
    assert out['authorizes_location'] is out['alignment_eligible'] is False


def test_current_only_record_has_conditional_models_without_invented_voltage(tmp_path):
    p=source_fixture(tmp_path)
    obs=api('comtrade.source_observations','load_source')(p)
    obs['channels']=obs['channels'][3:]
    out=api('dsp.source_analysis','analyse_source')(obs)
    assert out['windows'][0]['frequency']['status']=='estimated'
    assert out['windows'][0]['frequency_basis']=='phase current; voltage reference unavailable'
    assert out['windows'][0]['channels']['A4']['status']=='model_consistent'


def test_extreme_declared_duration_degrades_to_samples_without_overflow(tmp_path):
    p=source_fixture(tmp_path)
    obs=api('comtrade.source_observations','load_source')(p)
    obs['axis']['elapsed_s']=(np.arange(obs['sample_count'])*1e303).tolist()
    out=api('dsp.source_analysis','analyse_source')(obs)
    assert out['status']=='sample_only' and out['channels']
    json.dumps(out,allow_nan=False)


def test_extreme_raw_amplitudes_still_render_a_finite_sample_plot(tmp_path):
    a=analysis(tmp_path)
    a['channels'][0].update(sample_min=-1e308,sample_max=1e308,trace=[[0,-1e308],[10,1e308]])
    html=api('report.source_analysis','render_source_report')(api('dsp.source_compare','compare_sources')([a]))
    assert not re.search(r'\b(?:nan|inf)\b',html)


def test_orphan_cfg_still_shows_parsed_station_and_header_hash(tmp_path):
    p=source_fixture(tmp_path)
    p.with_suffix('.dat').unlink()
    obs=api('comtrade.source_observations','load_source')(p)
    assert obs['status']=='cfg_only' and obs['station']=='Synthetic'
    assert p.name in obs['source_sha256'] and obs['sample_count']==0
