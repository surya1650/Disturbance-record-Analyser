"""Source snapshot and declared line facts; missing fields never get defaults."""
import copy
import hashlib
import math
import re
from pathlib import Path

import yaml

from .source_inspection import inspection_record


def _finite(value):
    return float(value) if type(value) in (int,float) and math.isfinite(value) else None


def line_facts(root,revision):
    result=revision.get('result') or {}
    out=dict(id='Not available',name='Not available',length_km=None,kv=None,
        terminals=dict(S='Not available',R='Not available'),sections=[],sha256=None,
        parameter_status='Not available',provenance='No frozen line definition supplied for this revision.',
        location=dict(status='Not available',text='Line/model and eligible location evidence are not supplied.',km_from_S=None))
    saved=result.get('line_snapshot')
    if not saved:
        return out
    allowed=(Path(root)/'runs'/revision['incident_id']/str(revision['number'])).resolve()
    path=Path(saved).resolve()
    if not path.is_relative_to(allowed) or not path.is_file() or path.stat().st_size>65536:
        out['provenance']='Frozen line definition is unavailable or outside its revision.'
        return out
    try:
        raw=path.read_bytes()
        data=yaml.safe_load(raw)
        if not isinstance(data,dict):
            return out
        terminals=data.get('terminals') or {}
        out.update(id=str(data.get('id') or 'Not available'),name=str(data.get('name') or 'Not available'),
            kv=_finite(data.get('kv')),sha256=hashlib.sha256(raw).hexdigest(),
            parameter_status=result.get('parameter_status') or 'unverified',
            provenance='Frozen revision line.yaml; declared values, not independent physical verification.')
        for end in ('S','R'):
            entry=terminals.get(end) or {}
            out['terminals'][end]=str(entry.get('substation') or 'Not available')
        previous=0.
        covered=True
        for section in data.get('sections') or []:
            lo,hi=_finite(section.get('from_km')),_finite(section.get('to_km'))
            good=lo is not None and hi is not None and hi>lo and abs(lo-previous)<1e-8
            covered=covered and good
            if hi is not None:
                previous=hi
            out['sections'].append(dict(from_km=lo,to_km=hi,**{key+'_ohm_per_km':_finite(section.get(key)) for key in ('r1','x1','r0','x0')}))
        out['length_km']=previous if covered and out['sections'] else None
        text=result.get('location_text') or ''
        match=re.match(r'^([0-9]+(?:\.[0-9]+)?) km from ',text)
        if match:
            km=float(match.group(1))
            eligible=(out['length_km'] is not None and 0<=km<=out['length_km'] and out['parameter_status']!='provisional' and not data.get('model_review_required',False))
            out['location'].update(status='Existing conditional estimate',text=text,km_from_S=km,overlay_eligible=eligible,
                provenance='Stored operational incident result; independent source fits and CT defaults do not validate this estimate.')
        elif text:
            out['location']['text']=text.removeprefix('refused - ')
        return out
    except (OSError,ValueError,TypeError,AttributeError,yaml.YAMLError):
        out['provenance']='Frozen line definition could not be read as declared line facts.'
        return out


def compose_snapshot(root,revision,filename,result, *, registry=None, resolved_line=None):
    from .source_diagnostics import diagnostic_identity
    from .source_lines import resolve_line
    line=copy.deepcopy(resolved_line if resolved_line is not None else resolve_line(root,revision,result['options'],registry))
    identity=diagnostic_identity(root,revision,filename,result['options'],registry=registry,resolved_line=line)
    if any(result.get(k)!=v for k,v in identity.items()):
        raise ValueError('Snapshot source/options binding differs from the current revision.')
    meta=inspection_record(root,revision,filename)
    return dict(**identity,title='Source analysis snapshot',decode_status=meta['status'],
        issues=meta['issues'],sample_count=meta['sample_count'],station=meta['station'],device=meta['device'],
        recorded_times=meta.get('recorded_times',{}),inferred_inception='Not available',
        time_basis=meta['time_basis'],inventory=meta['inventory'],sections=result['conclusions'],
        assumptions=result['assumptions'],scaling_notes=result['scaling_notes'],methods=result['methods'],
        line=line,fit_coverage=result['fit_coverage'],
        selected_projection=result.get('selected_projection'),
        authorizes_location=False,alignment_eligible=False,ct_vt_verified=False,
        note='Every claim is limited to its stated source, option and method evidence. Recorded trigger is not inferred fault inception or operation time.')
