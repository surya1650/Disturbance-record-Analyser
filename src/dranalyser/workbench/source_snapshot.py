"""Source snapshot and declared line facts; missing fields never get defaults."""
import copy
import hashlib
import json
import math
import re
from pathlib import Path

import yaml

from .source_inspection import inspection_record
from .location_summary import snapshot_location


def _finite(value):
    return float(value) if type(value) in (int,float) and math.isfinite(value) else None


def _declared_inputs(revision, out):
    from .incident_inputs import validate_incident_line
    from .line_reference_review import reference_provenance
    try:
        entry = validate_incident_line(revision)
    except ValueError:
        out['provenance'] = 'Saved line inputs are stale or need physical-end review; no model or distance is released.'
        return out
    if not entry:
        return out
    review = entry['review']
    reference = reference_provenance(review)
    if reference:
        out['line_reference'] = reference
    labels = {end: (review['ends'].get(end) or {}).get('name') or 'Not available' for end in ('S', 'R')}
    out.update(id=entry['line_id'], name=' — '.join(v for v in labels.values() if v != 'Not available') or 'Saved incident line inputs',
        length_km=review.get('length_km'), kv=review.get('kv'), terminals=labels,
        parameter_status='draft; user supplied, unverified',
        sha256=hashlib.sha256(json.dumps(entry, sort_keys=True, allow_nan=False).encode()).hexdigest(),
        provenance='Saved source-bound incident input revision; declared facts, not a frozen operational estimate.')
    out['sections'] = copy.deepcopy(review.get('sections') or [])
    if not out['sections'] and review.get('length_km'):
        divisor = review['length_km'] if review.get('basis') == 'total' else 1 if review.get('basis') == 'per-km' else None
        out['sections'] = [dict(from_km=0., to_km=review['length_km'], **{
            key+'_ohm_per_km': _finite(review[key]/divisor) if review.get(key) is not None and divisor else None
            for key in ('r1', 'x1', 'r0', 'x0')})]
    out['location'].update(text='Saved line facts are available; an eligible operational fault-distance result has not been calculated.',
                           overlay_eligible=False)
    return out


def line_facts(root,revision):
    result=revision.get('result') or {}
    out=dict(id='Not available',name='Not available',length_km=None,kv=None,
        terminals=dict(S='Not available',R='Not available'),sections=[],sha256=None,
        parameter_status='Not available',provenance='No frozen line definition supplied for this revision.',
        location=dict(status='Not available',text='Line/model and eligible location evidence are not supplied.',km_from_S=None))
    saved=result.get('line_snapshot')
    if not saved:
        if not result.get('location_summary') and (revision.get('metadata') or {}).get('incident_line'):
            return _declared_inputs(revision, out)
        if 'location_summary' in result:
            out['location']=snapshot_location(result['location_summary'],revision,None,None,False,result.get('location_text',''))
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
        review_provenance = data.get('review_provenance')
        reference = review_provenance.get('line_reference') if isinstance(review_provenance, dict) else None
        if isinstance(reference, dict) and reference:
            out['line_reference'] = copy.deepcopy(reference)
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
        if 'location_summary' in result:
            eligible=out['parameter_status']!='provisional' and not data.get('model_review_required',False)
            out['location']=snapshot_location(result['location_summary'],revision,out['sha256'],out['length_km'],eligible,text)
            return out
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
