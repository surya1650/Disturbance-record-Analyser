"""Bounded, explicit line-model declarations; never inferred corridor identity."""
import hashlib
import json
import math
from pathlib import Path

import yaml

CONSTANTS=('r1_ohm_per_km','x1_ohm_per_km','r0_ohm_per_km','x0_ohm_per_km')
MODEL_KEYS={'length_km','name','provenance','kv','sections',*CONSTANTS}


def _number(value):
    try:
        return float(value) if type(value) in (int,float) and math.isfinite(value) else None
    except OverflowError:
        return None


def normalise_model(raw):
    if not isinstance(raw,dict) or set(raw)-MODEL_KEYS:
        raise ValueError('Custom line model accepts explicit length, V/A-independent line constants, sections, name and provenance only.')
    out={}
    for key,value in sorted(raw.items()):
        if key in ('name','provenance'):
            if not isinstance(value,str) or len(value)>1000:
                raise ValueError('Line name/provenance must be text of at most1000 characters.')
            out[key]=value
        elif key=='sections':
            if not isinstance(value,list) or len(value)>128:
                raise ValueError('Supply at most128 explicit line sections.')
            sections=[]
            for section in value:
                if not isinstance(section,dict) or set(section)-{'from_km','to_km',*CONSTANTS}:
                    raise ValueError('Line section accepts explicit kilometre coordinates and ohm/km constants only.')
                cleaned={}
                for field,item in sorted(section.items()):
                    if item is not None and _number(item) is None:
                        raise ValueError('Line section numbers must be finite numeric values or unknown.')
                    cleaned[field]=_number(item)
                sections.append(cleaned)
            out[key]=sections
        else:
            if value is not None and _number(value) is None:
                raise ValueError('Line numbers must be finite numeric values or unknown.')
            out[key]=_number(value)
    return out


def _empty():
    return dict(id='Not available',name='Not available',kv=None,length_km=None,constants={},sections=[],
        terminals={'S':'Not available','R':'Not available'},parameter_status='unverified',sha256=None,issues=[],
        provenance='No independent line model supplied.',
        location=dict(status='Not available',text='Choose a supported window and supply a line/fault-loop model.',km_from_S=None))


def _custom_line(model):
    out=_empty()
    length=model.get('length_km')
    out.update(id='USER-MODEL',name=model.get('name') or 'User supplied line model',
        kv=model.get('kv'),length_km=length if length is not None and length>0 else None,
        constants={k:model.get(k) for k in CONSTANTS},parameter_status='user supplied; unverified',
        provenance=model.get('provenance') or 'Explicit user supplied line model; physical validation not supplied.',
        sha256=hashlib.sha256(json.dumps(model,sort_keys=True).encode()).hexdigest())
    out['sections']=model.get('sections') or ([dict(from_km=0.,to_km=length,**out['constants'])] if length is not None and length>0 else [])
    if length is not None and length<=0:
        out['issues'].append('Provided line length is not positive; full length remains Not available.')
    return out


def _registry_line(path,root):
    resolved=path.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file() or resolved.stat().st_size>65536:
        raise ValueError('Configured line source is outside its registry or exceeds the64KiB budget.')
    raw=resolved.read_bytes()
    data=yaml.safe_load(raw)
    if not isinstance(data,dict):
        raise ValueError('Configured line source must be a mapping of declared fields.')
    out=_empty()
    out.update(id=str(data.get('id') or ''),name=str(data.get('name') or path.name),kv=_number(data.get('kv')),
        sha256=hashlib.sha256(raw).hexdigest(),source_file=path.name,
        parameter_status='provisional' if data.get('model_review_required') or 'PROVISIONAL' in raw.decode('utf-8',errors='replace').upper() else 'unverified',
        provenance='User-selected configured line model '+path.name+'; association and physical constants are unverified.')
    terminals=data.get('terminals') or {}
    if isinstance(terminals,dict):
        for end in ('S','R'):
            value=terminals.get(end) or {}
            if isinstance(value,dict) and value.get('substation'):
                out['terminals'][end]=str(value['substation'])
    sections=data.get('sections') or []
    if not isinstance(sections,list) or len(sections)>128:
        raise ValueError('Configured line must contain at most128 declared sections.')
    previous=0.
    complete=bool(sections)
    for part in sections:
        if not isinstance(part,dict):
            raise ValueError('Configured line sections must contain declared coordinate/constant fields.')
        lo,hi=_number(part.get('from_km')),_number(part.get('to_km'))
        complete=complete and lo is not None and hi is not None and hi>lo and abs(lo-previous)<1e-8
        if hi is not None:
            previous=hi
        out['sections'].append(dict(from_km=lo,to_km=hi,**{key+'_ohm_per_km':_number(part.get(key)) for key in ('r1','x1','r0','x0')}))
    out['length_km']=previous if complete else None
    return out


def registry_line_models(registry):
    if registry is None:
        return []
    root=Path(registry).resolve()
    paths=sorted(root.glob('*.yaml'))
    if len(paths)>512:
        raise ValueError('Line registry exceeds512source files; narrow the configured registry.')
    rows=[]
    for path in paths:
        try:
            rows.append(_registry_line(path,root))
        except (OSError,ValueError,yaml.YAMLError) as exc:
            rows.append(dict(id='',name=path.name,issues=[str(exc)]))
    return rows


def resolve_line(root,revision,options,registry=None):
    if options.get('line_model'):
        return _custom_line(options['line_model'])
    if options.get('line_id'):
        matches=[line for line in registry_line_models(registry) if line.get('id')==options['line_id']]
        if len(matches)!=1:
            raise ValueError('Selected line must resolve to exactly one contained configured model.')
        return matches[0]
    from .source_snapshot import line_facts
    return line_facts(root,revision)
