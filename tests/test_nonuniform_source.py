"""Analytic expectations do not call the production signal builder or fitter."""
import importlib
import json

import numpy as np
import pytest

from tests.test_timestamp_recovery import write_timing


def api(module, name):
    return getattr(importlib.import_module('dranalyser.'+module), name)


def wave():
    t = np.r_[0,np.cumsum(np.resize([.000817,.000833,.000830],119))]
    u = t-(t[0]+t[-1])/2
    y = np.sqrt(2)*100*np.cos(2*np.pi*50.2*u+.2)
    return t,y+20+7*u+15*np.cos(2*np.pi*100.4*u+.7)


def test_irregular_joint_fit_retains_fundamental_with_harmonic_and_trend():
    t,y = wave()
    out = api('dsp.nonuniform','fit_source_window')(t,y,50.2)
    assert out['status']=='model_consistent'
    assert out['rms']==pytest.approx(100,rel=1e-10)
    assert complex(*out['phasor'])==pytest.approx(100*np.exp(.2j),rel=1e-10)
    assert out['relative_residual']<1e-10
    assert out['authorizes_location'] is out['alignment_eligible'] is False
    json.dumps(out,allow_nan=False)


def test_frequency_is_estimated_on_actual_times_without_nominal_fallback():
    t,y=wave()
    out=api('dsp.nonuniform','source_frequency')(t,y[:,None],50)
    assert out['status']=='estimated'
    assert out['frequency_hz']==pytest.approx(50.2,abs=1e-4)


@pytest.mark.parametrize('kind',['masked','nan','complex','bool','gap','collapsed','huge','short','string'])
def test_unusable_samples_cannot_create_a_model(kind):
    t,y=wave()
    if kind=='masked':
        y=np.ma.array(y,mask=np.arange(len(y))==7)
    elif kind=='nan':
        y[7]=np.nan
    elif kind=='complex':
        y=y+1j
    elif kind=='bool':
        y=y>0
    elif kind=='gap':
        t[60:]+=.02
    elif kind=='collapsed':
        t[60]=t[59]
    elif kind=='huge':
        y*=1e300
    elif kind=='short':
        t,y=t[:10],y[:10]
    else:
        y=y.astype(str)
    out=api('dsp.nonuniform','fit_source_window')(t,y,50)
    assert out['status']=='withheld'
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('frequency',[45,55])
def test_frequency_at_search_boundary_is_not_a_supported_estimate(frequency):
    t,_=wave()
    y=np.cos(2*np.pi*frequency*t)
    assert api('dsp.nonuniform','source_frequency')(t,y[:,None],50)['status']=='withheld'


def test_flat_reference_does_not_invent_nominal_frequency():
    t,_=wave()
    assert api('dsp.nonuniform','source_frequency')(t,np.ones((len(t),1)),50)['status']=='withheld'


def source_fixture(tmp_path,n=360,*,nrates=0):
    ts=np.r_[0,np.cumsum(np.resize([817,833,830],n-1))]
    write_timing(tmp_path,ts,nrates=nrates)
    p=tmp_path/'timing.cfg'
    t=ts*1e-6
    columns=np.stack([100*np.cos(2*np.pi*49.7*t+k) for k in range(6)],axis=1)
    p.with_suffix('.dat').write_text(''.join(','.join(map(str,[i+1,ts[i],*columns[i]]))+'\n'
        for i in range(n)),encoding='ascii')
    return p


def test_loader_and_pipeline_analyse_nonuniform_single_end_without_sync(tmp_path):
    p=source_fixture(tmp_path)
    obs=api('comtrade.source_observations','load_source')(p)
    out=api('dsp.source_analysis','analyse_source')(obs)
    assert obs['axis']['status']=='source_time_inspection'
    assert out['windows_evaluated']>0 and out['coverage_complete']
    assert any(w['channels']['A1']['status']=='model_consistent' for w in out['windows'])
    assert out['alignment_eligible'] is out['authorizes_location'] is out['authorizes_production_dsp'] is False
    assert out['channels'][0]['units']=='V (CFG-declared, unverified)'
    json.dumps(out,allow_nan=False)


def test_missing_ascii_signal_is_not_observed_zero(tmp_path):
    p=source_fixture(tmp_path)
    path=p.with_suffix('.dat')
    rows=path.read_text().splitlines()
    row=rows[50].split(',')
    row[2]=''
    rows[50]=','.join(row)
    path.write_text('\n'.join(rows)+'\n')
    obs=api('comtrade.source_observations','load_source')(p)
    assert obs['channels'][0]['values'][50] is None
    out=api('dsp.source_analysis','analyse_source')(obs)
    assert out['channels'][0]['missing_samples']==1
    assert any(w['channels']['A1']['status']=='withheld' for w in out['windows'])


def test_invalid_timing_retains_sample_statistics_without_timed_model(tmp_path):
    p=source_fixture(tmp_path)
    path=p.with_suffix('.dat')
    rows=path.read_text().splitlines()
    row=rows[50].split(',')
    row[1]=''
    rows[50]=','.join(row)
    path.write_text('\n'.join(rows)+'\n')
    out=api('dsp.source_analysis','analyse_source')(api('comtrade.source_observations','load_source')(p))
    assert out['status']=='sample_only' and out['windows_evaluated']==0
    assert out['channels'][0]['finite_samples']==360


def test_invalid_scaling_keeps_raw_counts_instead_of_default_gain(tmp_path):
    p=source_fixture(tmp_path)
    lines=p.read_text().splitlines()
    row=lines[2].split(',')
    row[5]=''
    lines[2]=','.join(row)
    p.write_text('\n'.join(lines)+'\n')
    obs=api('comtrade.source_observations','load_source')(p)
    assert obs['channels'][0]['units']=='raw counts'
    assert obs['channels'][0]['values'][0]==100


def test_truncated_row_withholds_timing_instead_of_padding_observed_zero(tmp_path):
    p=source_fixture(tmp_path)
    path=p.with_suffix('.dat')
    rows=path.read_text().splitlines()
    rows[-1]=','.join(rows[-1].split(',')[:-1])
    path.write_text('\n'.join(rows)+'\n')
    obs=api('comtrade.source_observations','load_source')(p)
    assert obs['axis']['status']=='withheld' and obs['issues']
    assert obs['channels'][-1]['values'][-1] is None


def test_window_budget_exposes_unanalysed_remainder(tmp_path):
    p=source_fixture(tmp_path,n=800)
    out=api('dsp.source_analysis','analyse_source')(api('comtrade.source_observations','load_source')(p),max_windows=1)
    assert out['windows_evaluated']==1 and out['windows_planned']>1
    assert out['remaining_windows']==out['windows_planned']-1 and not out['coverage_complete']


def test_constant_declared_rate_does_not_require_dat_clock(tmp_path):
    p=source_fixture(tmp_path,nrates=1)
    obs=api('comtrade.source_observations','load_source')(p)
    assert obs['axis']['status']=='source_time_inspection'
    assert obs['axis']['elapsed_s'][1]==pytest.approx(1/1200)


def test_malformed_cfg_returns_visible_unsupported_result(tmp_path):
    p=source_fixture(tmp_path)
    lines=p.read_text().splitlines()
    lines[2]='1,too,short'
    p.write_text('\n'.join(lines)+'\n')
    out=api('comtrade.source_observations','load_source')(p)
    assert out['status']=='unsupported' and out['issues']
    json.dumps(out,allow_nan=False)


def test_mixed_boolean_is_not_a_measured_signal_value():
    t,_=wave()
    y=list(np.cos(2*np.pi*50.2*(t-t[7])))
    y[7]=True
    assert api('dsp.nonuniform','fit_source_window')(t,y,50.2)['status']=='withheld'


def test_unrepresentable_secondary_ratio_is_not_measured_zero(tmp_path):
    p=source_fixture(tmp_path)
    lines=p.read_text().splitlines()
    row=lines[2].split(',')
    row[10:13]=['1e-300','1e300','S']
    lines[2]=','.join(row)
    p.write_text('\n'.join(lines)+'\n')
    out=api('comtrade.source_observations','load_source')(p)
    assert out['channels'][0]['units']=='raw counts'
    assert out['channels'][0]['values'][0]==100


@pytest.mark.parametrize('kind',['BINARY','BINARY32','FLOAT32'])
def test_declared_binary_payloads_decode_without_inventing_truncated_samples(tmp_path,kind):
    import struct
    p=source_fixture(tmp_path,n=96,nrates=1)
    p.write_text(p.read_text().replace('ASCII',kind))
    fmt={'BINARY':'h','BINARY32':'i','FLOAT32':'f'}[kind]
    raw=b''.join(struct.pack('<II'+6*fmt,i+1,0,1,2,3,4,5,6) for i in range(96))
    p.with_suffix('.dat').write_bytes(raw)
    out=api('comtrade.source_observations','load_source')(p)
    assert out['sample_count']==96 and out['channels'][0]['values'][0]==1
    p.with_suffix('.dat').write_bytes(raw[:-1])
    bad=api('comtrade.source_observations','load_source')(p)
    assert bad['status']=='unsupported' and bad['issues']
