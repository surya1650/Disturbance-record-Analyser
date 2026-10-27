"""Strict read-only source observations; missing samples never become zero."""
import hashlib
import math
from pathlib import Path

import numpy as np

from .parser import ComtradeError, DOS_EOF, _read_binary, detect_phase_naming, map_channel, parse_cfg
from .source_time import source_time_axis


def _number(value):
    try:
        v=float(value)
        return v if math.isfinite(v) else None
    except (ValueError,TypeError,OverflowError):
        return None


def _list(values):
    return [float(v) if np.isfinite(v) else None for v in values]


def load_source(cfg_path,dat_path=None):
    out=dict(status='unsupported',issues=[],channels=[],digital=[],sample_count=0,
             axis=dict(status='withheld',elapsed_s=[],reason='Source format not supported.'),
             content_hash='',authorizes_location=False,alignment_eligible=False)
    try:
        path=Path(cfg_path)
        data=Path(dat_path) if dat_path else next((p for p in (path.with_suffix('.DAT'),path.with_suffix('.dat'),
             path.with_suffix('.Dat')) if p.is_file()),path.with_suffix('.dat'))
        if path.suffix.lower()!='.cfg' or path.stat().st_size>1048576:
            raise ValueError('Unsupported source container or byte budget.')
        cfg_bytes=path.read_bytes()
        out['source_sha256']={path.name:hashlib.sha256(cfg_bytes).hexdigest()}
        text=cfg_bytes.decode('latin1').replace(DOS_EOF,'')
        lines=[line.strip() for line in text.splitlines() if line.strip()]
        counts=lines[1].split(',')
        na,nd=int(counts[1][:-1]),int(counts[2][:-1])
        if counts[1][-1:]!='A' or counts[2][-1:]!='D' or not 1<=na<=64 or not 0<=nd<=256 or int(counts[0])!=na+nd:
            raise ValueError('Unsupported channel counts.')
        j=2+na+nd
        nrates=int(lines[j+1])
        if not 0<=nrates<=8:
            raise ValueError('Unsupported rate table.')
        end=j+2+max(nrates,1)
        if end+2>=len(lines) or lines[end+2].upper() not in ('ASCII','BINARY','BINARY32','FLOAT32'):
            raise ValueError('Explicit supported DAT format required.')
        cfg=parse_cfg(text)
        out.update(station=cfg.station,device=cfg.device_id)
        if not data.is_file():
            out.update(status='cfg_only',issues=['CFG decoded; matching DAT file is missing.'],
                       axis=dict(status='withheld',elapsed_s=[],reason='No paired DAT observations.'))
            return out
        if data.stat().st_size>64*1024*1024:
            raise ValueError('Unsupported DAT byte budget.')
        dat_bytes=data.read_bytes()
        out['content_hash']=hashlib.sha256(cfg_bytes+dat_bytes).hexdigest()
        out['source_sha256'][data.name]=hashlib.sha256(dat_bytes).hexdigest()
        if cfg.file_type=='ASCII':
            rows=[row.split(',') for row in dat_bytes.decode('latin1').replace(DOS_EOF,'').splitlines() if row.strip()]
            if not 3<=len(rows)<=200000 or len(rows)*(2+na+nd)>4000000:
                raise ValueError('Unsupported sample budget.')
            cols=np.full((len(rows),2+na+nd),np.nan)
            bad_width=sum(len(row)!=cols.shape[1] for row in rows)
            for i,row in enumerate(rows):
                for k,cell in enumerate(row[:cols.shape[1]]):
                    value=_number(cell)
                    if value is not None:
                        cols[i,k]=value
            if bad_width:
                out['issues'].append(f'{bad_width} DAT rows have a mismatched column count; no timing model.')
            numbers,stamps,values=cols[:,0],cols[:,1],cols[:,2:]
        else:
            width={'BINARY':2,'BINARY32':4,'FLOAT32':4}[cfg.file_type]
            rowbytes=8+na*width+2*((nd+15)//16)
            if (len(dat_bytes)%rowbytes or not 3<=len(dat_bytes)//rowbytes<=200000
                    or len(dat_bytes)//rowbytes*(2+na+nd)>4000000):
                raise ValueError('Truncated/unsupported binary payload; no partial decode.')
            numbers,stamps,values=_read_binary(dat_bytes,na,nd,cfg.file_type)
        n=len(numbers)
        declared=int(lines[j+2+max(nrates,1)-1].split(',')[1])
        if n!=declared:
            out['issues'].append('Actual and declared sample counts differ; no timing model.')
        nominal=_number(lines[j])
        multiplier=_number(lines[end+3]) if end+3<len(lines) else None
        axis=source_time_axis(numbers,stamps,nrates=nrates,timemult=multiplier)
        if nrates==1:
            rate=_number(lines[j+2].split(',')[0])
            if rate is not None and 1<=rate<=1e9:
                axis=source_time_axis(numbers,np.arange(n),nrates=0,timemult=1e6/rate)
                axis['basis']='Explicit single CFG sample rate; DAT timestamps are noncritical.'
        if out['issues']:
            axis=dict(status='withheld',elapsed_s=[],reason='Structural source defects; inspect samples only.')
        out.update(status='observed' if axis['status']=='source_time_inspection' else 'sample_only',
            station=cfg.station,device=cfg.device_id,nominal_frequency_hz=nominal,
            sample_count=n,sample_numbers=_list(numbers),axis=axis)
        naming=detect_phase_naming([a.ch_id for a in cfg.analogs])
        for i in range(na):
            fields=[v.strip() for v in lines[2+i].split(',')]
            fields+=['']*max(0,13-len(fields))
            a,b,skew,primary,secondary=map(_number,[fields[k] for k in (5,6,7,10,11)])
            unit=fields[4].upper()
            gain=1000 if unit in ('KV','KA') else 1
            valid=a is not None and b is not None and unit in ('V','A','KV','KA') and fields[12].upper() in ('P','S')
            ratio=1
            if fields[12].upper()=='S':
                valid=valid and primary is not None and secondary is not None and primary>0 and secondary>0
                ratio=primary/secondary if valid else 1
            if valid:
                factor=a*ratio*gain
                valid=math.isfinite(factor) and abs(factor)>=np.finfo(float).tiny
            vals=values[:,i]
            if valid:
                with np.errstate(over='ignore',invalid='ignore'):
                    converted=(vals*a+b)*ratio*gain
                valid=bool(np.all(np.isfinite(converted[np.isfinite(vals)])))
                if valid:
                    vals=converted
            out['channels'].append(dict(key=f'A{i+1}',label=fields[1],
                units=(('V' if unit.endswith('V') else 'A')+' (CFG-declared, unverified)') if valid else 'raw counts',
                values=_list(vals),frequency_reference=map_channel(fields[1],unit,fields[2],naming) in ('VA','VB','VC'),skew_us=skew,
                current_reference=map_channel(fields[1],unit,fields[2],naming) in ('IA','IB','IC'),
                scaling_verified=False))
        for i,label in enumerate(cfg.digitals):
            bits=values[:,na+i]
            out['digital'].append(dict(key=f'D{i+1}',label=label,
                states=[int(v) if v in (0,1) else None for v in bits]))
        return out
    except (ComtradeError,ValueError,TypeError,IndexError,KeyError,OSError,OverflowError) as exc:
        out.update(status='unsupported',channels=[],digital=[],sample_count=0,
                   axis=dict(status='withheld',elapsed_s=[],reason='Source decode unavailable.'))
        out['issues'].append(str(exc))
        return out
