"""Deliberate recovery retains exact observations and opaque bytes, never zeros."""
import hashlib
import json
import struct

import pytest

from dranalyser.comtrade.source_observations import load_source


def record(tmp_path,*,analog=1,digital=1,n=3,kind='ASCII',numbers=None):
    cfg=tmp_path/'source.cfg'
    lines=['PUBLIC,RECOVERY,2013',f'{analog+digital},{analog}A,{digital}D']
    lines += [f'{i+1},A{i+1},A,,A,2,1,0,-32767,32767,1,1,P' for i in range(analog)]
    lines += [f'{i+1},D{i+1},,,0' for i in range(digital)]
    lines += ['50','1',f'1000,{n}','01/01/2020,00:00:00.000000','01/01/2020,00:00:00.000000',kind,'1']
    cfg.write_text('\n'.join(lines)+'\n')
    numbers=numbers or list(range(1,n+1))
    if kind=='ASCII':
        data=''.join(','.join(map(str,[numbers[i],i*1000,*([10+i]*analog),*([i%2]*digital)]))+'\n' for i in range(n)).encode()
    else:
        fmt={'BINARY':'h','BINARY32':'i','FLOAT32':'f'}[kind]
        data=b''.join(struct.pack('<II'+fmt*analog+'H'*((digital+15)//16),numbers[i],i*1000,*([10+i]*analog),*([65535 if i%2 else 0]*((digital+15)//16))) for i in range(n))
    cfg.with_suffix('.dat').write_bytes(data)
    return cfg


@pytest.mark.parametrize('kind',['ASCII','BINARY','BINARY32','FLOAT32'])
def test_digital_only_sources_retain_native_states_without_analog_requirements(tmp_path,kind):
    cfg=record(tmp_path,analog=0,digital=2,kind=kind)
    out=load_source(cfg)
    assert out['sample_count']==3 and out['channels']==[]
    assert [c['states'] for c in out['digital']]==[[0,1,0],[0,1,0]]
    assert out['authorizes_location'] is out['alignment_eligible'] is False


@pytest.mark.parametrize('n',[1,2])
@pytest.mark.parametrize('kind',['ASCII','BINARY','BINARY32','FLOAT32'])
def test_one_and_two_sample_records_are_inspectable_without_invented_time(tmp_path,n,kind):
    cfg=record(tmp_path,n=n,kind=kind)
    out=load_source(cfg)
    assert out['sample_count']==n
    assert out['channels'][0]['values']==[21,23][:n]
    assert out['digital'][0]['states']==[0,1][:n]
    assert out['axis']['status']=='withheld' and out['axis']['elapsed_s']==[]
    assert out['status']=='sample_only'


@pytest.mark.parametrize('kind',['BINARY','BINARY32','FLOAT32'])
def test_truncated_binary_recovers_only_complete_counter_consistent_prefix(tmp_path,kind):
    cfg=record(tmp_path,n=4,kind=kind)
    dat=cfg.with_suffix('.dat')
    dat.write_bytes(dat.read_bytes()[:-1])
    raw=dat.read_bytes()
    out=load_source(cfg)
    assert out['sample_count']==3
    assert out['channels'][0]['values']==[21,23,25]
    assert out['digital'][0]['states']==[0,1,0]
    assert out['axis']['status']=='withheld'
    assert out['recovery']['decoded_samples']==3 and out['recovery']['opaque_bytes']>0
    assert out['source_sha256'][dat.name]==hashlib.sha256(raw).hexdigest()
    assert out['issues'] and not out['authorizes_location']


def test_partial_binary_stops_before_an_unreliable_counter_alignment(tmp_path):
    cfg=record(tmp_path,n=4,kind='BINARY',numbers=[1,2,99,100])
    dat=cfg.with_suffix('.dat')
    dat.write_bytes(dat.read_bytes()+b'x')
    out=load_source(cfg)
    assert out['sample_count']==2
    assert out['channels'][0]['values']==[21,23]
    assert out['recovery']['opaque_bytes']==25
    assert out['axis']['status']=='withheld'


def test_aligned_counter_gap_keeps_existing_sample_index_observations(tmp_path):
    cfg=record(tmp_path,n=3,kind='BINARY',numbers=[1,2,9])
    # An explicit CFG rate is noncritical to these counter fields in the existing
    # declared-rate source-coordinate contract; no new timing policy is asserted.
    out=load_source(cfg)
    assert out['sample_count']==3 and out['channels'][0]['values']==[21,23,25]


def test_empty_or_first_partial_row_has_no_fabricated_sample(tmp_path):
    cfg=record(tmp_path,n=1,kind='BINARY')
    dat=cfg.with_suffix('.dat')
    for raw in (b'',b'\x01\x00\x00'):
        dat.write_bytes(raw)
        out=load_source(cfg)
        assert out['sample_count']==0 and out['channels']==[] and out['issues']
        assert 'complete' in ' '.join(out['issues']).lower() or 'empty' in ' '.join(out['issues']).lower()
        json.dumps(out,allow_nan=False)


def test_short_ascii_missing_observations_stay_unknown(tmp_path):
    cfg=record(tmp_path,n=1)
    cfg.with_suffix('.dat').write_text('1,0,,\n')
    out=load_source(cfg)
    assert out['sample_count']==1
    assert out['channels'][0]['values']==[None] and out['digital'][0]['states']==[None]
    assert out['source_sha256'][cfg.name]==hashlib.sha256(cfg.read_bytes()).hexdigest()


def test_zero_channel_layout_is_explicitly_unsupported(tmp_path):
    out=load_source(record(tmp_path,analog=0,digital=0))
    assert out['status']=='unsupported' and out['sample_count']==0 and out['issues']
