"""User-visible regressions reproduced by the one fresh whole-branch review."""
import json
import struct

import numpy as np
import pytest

from tests.test_nonuniform_source import api,source_fixture


@pytest.mark.parametrize('coherent',[False,True])
def test_1999_missing_ascii_marker_never_becomes_an_observed_amplitude(tmp_path,coherent):
    p=source_fixture(tmp_path,n=97)
    lines=p.read_text().splitlines()[:-2]
    lines[0]=lines[0].replace('2013','1999')
    p.write_text('\n'.join(lines)+'\n')
    dat=p.with_suffix('.dat')
    rows=dat.read_text().splitlines()
    for i,text in enumerate(rows):
        fields=text.split(',')
        if coherent:
            fields[2]=str(99999*np.cos(2*np.pi*50.2*float(fields[1])*1e-6))
        elif i==0:
            fields[2]='99999'
        rows[i]=','.join(fields)
    dat.write_text('\n'.join(rows)+'\n')
    obs=api('comtrade.source_observations','load_source')(p)
    assert obs['channels'][0]['values'][0] is None
    assert api('dsp.source_analysis','analyse_source')(obs)['channels'][0]['missing_samples']>=1


def test_2013_ascii_99999_is_preserved_as_a_legitimate_numeric_value(tmp_path):
    p=source_fixture(tmp_path)
    dat=p.with_suffix('.dat')
    rows=dat.read_text().splitlines()
    fields=rows[0].split(',')
    fields[2]='99999'
    rows[0]=','.join(fields)
    dat.write_text('\n'.join(rows)+'\n')
    assert api('comtrade.source_observations','load_source')(p)['channels'][0]['values'][0]==99999


@pytest.mark.parametrize('kind,fmt,marker',[('BINARY','h',-32768),('BINARY32','i',-2147483648),
    ('FLOAT32','f',float(np.finfo(np.float32).min))])
def test_binary_missing_marker_is_masked_before_scaling(tmp_path,kind,fmt,marker):
    p=source_fixture(tmp_path,n=96)
    p.write_text(p.read_text().replace('ASCII',kind))
    raw=b''.join(struct.pack('<II'+6*fmt,i+1,i*833,marker if i==0 else 1,2,3,4,5,6) for i in range(96))
    p.with_suffix('.dat').write_bytes(raw)
    obs=api('comtrade.source_observations','load_source')(p)
    assert obs['channels'][0]['values'][0] is None and obs['channels'][0]['values'][1]==1


@pytest.mark.parametrize('nrates',[0,1])
def test_binary_missing_timestamp_is_not_a_declared_dat_coordinate(tmp_path,nrates):
    p=source_fixture(tmp_path,n=96,nrates=nrates)
    p.write_text(p.read_text().replace('ASCII','BINARY'))
    raw=b''.join(struct.pack('<II6h',i+1,0xFFFFFFFF if i==95 else i*833,1,2,3,4,5,6) for i in range(96))
    p.with_suffix('.dat').write_bytes(raw)
    obs=api('comtrade.source_observations','load_source')(p)
    assert obs['axis']['status']==('withheld' if nrates==0 else 'source_time_inspection')


@pytest.mark.parametrize('cut,index',[(49,0),(96,2)])
def test_gaps_at_either_requested_window_boundary_remain_visible(tmp_path,cut,index):
    t=np.r_[np.arange(cut)/1200,np.arange(cut,289)/1200+.04]
    obs=api('comtrade.source_observations','load_source')(source_fixture(tmp_path,n=len(t)))
    obs['axis']['elapsed_s']=t.tolist()
    for channel in obs['channels']:
        channel['values']=np.cos(2*np.pi*50.2*t).tolist()
    out=api('dsp.source_analysis','analyse_source')(obs)
    window=out['windows'][index]
    assert window['channels']['A1']['status']=='withheld'
    assert window['coverage_status']=='withheld' and window['observed_support_s']!=window['support_s']


def test_second_harmonic_only_reference_cannot_establish_fundamental_frequency():
    t=np.arange(121)/1200
    out=api('dsp.nonuniform','source_frequency')(t,np.cos(2*np.pi*100.4*t),50)
    assert out['status']=='withheld'


def test_unobservable_voltage_uses_and_displays_current_reference(tmp_path):
    obs=api('comtrade.source_observations','load_source')(source_fixture(tmp_path))
    t=np.array(obs['axis']['elapsed_s'])
    for i,c in enumerate(obs['channels']):
        c['values']=np.cos(2*np.pi*(100.4 if i<3 else 50.2)*t).tolist()
    out=api('dsp.source_analysis','analyse_source')(obs)
    assert out['windows'][0]['frequency_basis']=='phase current; voltage reference unavailable'
    review=api('dsp.source_compare','compare_sources')([out])
    assert 'phase current; voltage reference unavailable' in api('report.source_analysis','render_source_report')(review)


def test_local_reference_shifts_display_supports_without_changing_native_coordinates(tmp_path):
    out=api('dsp.source_analysis','analyse_source')(api('comtrade.source_observations','load_source')(source_fixture(tmp_path)))
    second=json.loads(json.dumps(out))
    second['content_hash']='different'
    n=out['sample_count']
    for record,k in ((out,10),(second,20)):
        record['digital']=[dict(key='D1',label='Start',states=[0]*k+[1]*5+[0]*(n-k-5))]
    result=api('dsp.source_compare','compare_sources')([out,second],reference='Start')
    for row,k in zip(result['records'],(10,20),strict=True):
        offset=row['axis']['elapsed_s'][k]
        assert row['windows'][0]['display_support_s']==pytest.approx([-offset,.08-offset])
        assert row['windows'][0]['support_s']==[0,.08]
        assert row['digital_intervals'][0]['display_start_s']==0
        assert row['trace_reference_s']==offset
    assert result['alignment_eligible'] is result['pairing_verified'] is False
    assert 'Relative to local reference' in api('report.source_analysis','render_source_report')(result)
    assert 'display_support_s' not in out['windows'][0]


@pytest.mark.parametrize('encoding',['utf-8','utf-8-sig','latin1'])
def test_unicode_label_survives_decode_anchor_selection_and_html(tmp_path,encoding):
    p=source_fixture(tmp_path)
    lines=p.read_text().splitlines()
    lines[1]='7,6A,1D'
    lines.insert(8,'1,Départ <&, , ,0')
    p.write_text('\n'.join(lines)+'\n',encoding=encoding)
    dat=p.with_suffix('.dat')
    dat.write_text('\n'.join(row+(',1' if 10<=i<15 else ',0') for i,row in enumerate(dat.read_text().splitlines()))+'\n')
    obs=api('comtrade.source_observations','load_source')(p)
    assert obs['station']=='Synthetic'
    result=api('dsp.source_compare','compare_sources')([api('dsp.source_analysis','analyse_source')(obs)],reference='Départ <&')
    assert result['records'][0]['local_reference']['sample_index']==10
    html=api('report.source_analysis','render_source_report')(result)
    assert 'Départ &lt;&amp;' in html


def test_nonzero_ascii_underflow_does_not_become_observed_zero(tmp_path):
    p=source_fixture(tmp_path)
    dat=p.with_suffix('.dat')
    rows=dat.read_text().splitlines()
    fields=rows[0].split(',')
    fields[2]='1e-999'
    rows[0]=','.join(fields)
    dat.write_text('\n'.join(rows)+'\n')
    assert api('comtrade.source_observations','load_source')(p)['channels'][0]['values'][0] is None


def test_current_only_frequency_basis_is_visible_in_html(tmp_path):
    obs=api('comtrade.source_observations','load_source')(source_fixture(tmp_path))
    obs['channels']=obs['channels'][3:]
    out=api('dsp.source_analysis','analyse_source')(obs)
    assert out['windows'][0]['frequency_basis']=='phase current; voltage reference unavailable'
    assert 'phase current; voltage reference unavailable' in api('report.source_analysis','render_source_report')(
        api('dsp.source_compare','compare_sources')([out]))


def test_engineering_conversion_underflow_keeps_original_raw_counts(tmp_path):
    p=source_fixture(tmp_path)
    lines=p.read_text().splitlines()
    fields=lines[2].split(',')
    fields[5]='.001'
    lines[2]=','.join(fields)
    p.write_text('\n'.join(lines)+'\n')
    dat=p.with_suffix('.dat')
    rows=dat.read_text().splitlines()
    fields=rows[0].split(',')
    fields[2]='1e-323'
    rows[0]=','.join(fields)
    dat.write_text('\n'.join(rows)+'\n')
    channel=api('comtrade.source_observations','load_source')(p)['channels'][0]
    assert channel['units']=='raw counts' and channel['values'][0]>0
