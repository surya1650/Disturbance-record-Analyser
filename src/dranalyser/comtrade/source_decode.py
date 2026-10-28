"""Strict bounded-byte observations; missing samples never become zero."""
import hashlib
import math
from decimal import Decimal,InvalidOperation

import numpy as np

from .parser import ComtradeError, DOS_EOF, _read_binary, detect_phase_naming, map_channel, parse_cfg
from .source_time import source_time_axis


def _number(value):
    try:
        v=float(value)
        if v==0 and Decimal(str(value))!=0:
            return None
        return v if math.isfinite(v) else None
    except (ValueError,TypeError,OverflowError,InvalidOperation):
        return None


def _list(values):
    return [float(v) if np.isfinite(v) else None for v in values]


def decode_source(cfg_bytes, dat_bytes=None, *, cfg_name, dat_name=None):
    out=dict(status='unsupported',issues=[],channels=[],digital=[],sample_count=0,
             axis=dict(status='withheld',elapsed_s=[],reason='Source format not supported.'),
             content_hash='',authorizes_location=False,alignment_eligible=False)
    try:
        out['source_sha256']={cfg_name:hashlib.sha256(cfg_bytes).hexdigest()}
        try:
            text=cfg_bytes.decode('utf-8-sig')
            out['text_encoding']='UTF-8 (optional BOM)'
        except UnicodeDecodeError:
            text=cfg_bytes.decode('latin1')
            out['text_encoding']='Legacy Latin-1 fallback; original bytes preserved'
        text=text.replace(DOS_EOF,'')
        lines=[line.strip() for line in text.splitlines() if line.strip()]
        counts=lines[1].split(',')
        na,nd=int(counts[1][:-1]),int(counts[2][:-1])
        if counts[1][-1:]!='A' or counts[2][-1:]!='D' or not 0<=na<=64 or na+nd==0 or not 0<=nd<=256 or int(counts[0])!=na+nd:
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
        if dat_bytes is None:
            out.update(status='cfg_only',issues=['CFG decoded; matching DAT file is missing.'],
                       axis=dict(status='withheld',elapsed_s=[],reason='No paired DAT observations.'))
            return out
        out['content_hash']=hashlib.sha256(cfg_bytes+dat_bytes).hexdigest()
        out['source_sha256'][dat_name]=hashlib.sha256(dat_bytes).hexdigest()
        if cfg.file_type=='ASCII':
            rows=[row.split(',') for row in dat_bytes.decode('latin1').replace(DOS_EOF,'').splitlines() if row.strip()]
            if not 1<=len(rows)<=200000 or len(rows)*(2+na+nd)>4000000:
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
            complete,remainder=divmod(len(dat_bytes),rowbytes)
            if complete==0:
                raise ValueError('No complete binary sample row; empty or truncated payload.')
            if complete>200000 or complete*(2+na+nd)>4000000:
                raise ValueError('Unsupported binary sample budget.')
            numbers,stamps,values=_read_binary(dat_bytes[:complete*rowbytes],na,nd,cfg.file_type)
            if remainder:
                safe=0
                if numbers[0] in (0,1):
                    safe=1
                    while safe<complete and numbers[safe]==numbers[safe-1]+1:
                        safe+=1
                if safe==0:
                    raise ValueError('No complete counter-consistent binary prefix; remaining bytes are opaque.')
                numbers,stamps,values=numbers[:safe],stamps[:safe],values[:safe]
                out['recovery']=dict(decoded_samples=safe,opaque_bytes=len(dat_bytes)-safe*rowbytes,
                    basis='Complete rows from byte zero; contiguous counters only. No offset search or row padding.')
                out['issues'].append(f'Partial binary payload: {safe} complete counter-consistent samples recovered; '
                    f'{len(dat_bytes)-safe*rowbytes} bytes remain opaque; no timing model.')
            stamps[stamps==0xFFFFFFFF]=np.nan
        edition=int(cfg.rev_year_raw) if cfg.rev_year_raw in ('1991','1999','2013') else cfg.edition
        marker=(99999 if edition==1999 else None) if cfg.file_type=='ASCII' else {
            'BINARY':-32768,'BINARY32':-2147483648,'FLOAT32':float(np.finfo(np.float32).min)}[cfg.file_type]
        if marker is not None:
            analog=values[:,:na]
            analog[analog==marker]=np.nan
        n=len(numbers)
        declared=int(lines[j+2+max(nrates,1)-1].split(',')[1])
        if 'recovery' in out:
            out['recovery']['declared_samples']=declared
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
                    product=vals*a
                    converted=(vals*a+b)*ratio*gain
                finite=np.isfinite(vals)
                underflow=finite & (vals!=0) & ((product==0) | (abs(product)<np.finfo(float).tiny))
                subnormal=(converted!=0) & (abs(converted)<np.finfo(float).tiny)
                valid=bool(np.all(np.isfinite(converted[finite])) and not np.any(underflow | subnormal))
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
