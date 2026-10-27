"""Independent supported source analysis with explicit, unverified assumptions."""
import hashlib
import json
import math

from ..comtrade.source_observations import _number
from ..dsp.source_analysis import analyse_source
from ..rules.signals import CANONICAL
from .channel_mapping import ANALOG_TARGETS
from .source_inspection import _source, _axis
from .source_events import digital_evidence, trip_ar


def normalise_options(options, source):
    options={} if options is None else options
    if not isinstance(options,dict) or set(options)-{'voltage_kv','mappings'}:
        raise ValueError('Analysis choices accept voltage_kv and channel mappings only.')
    kv=options.get('voltage_kv',0)
    if type(kv) is not int or kv not in (0,132,220):
        raise ValueError('Choose an unspecified, 132 kV or 220 kV voltage level.')
    mappings=options.get('mappings',{})
    if not isinstance(mappings,dict):
        raise ValueError('Channel meanings must be source-ID to meaning choices.')
    ids={c['key']:'analog' for c in source['channels']}|{c['key']:'digital' for c in source['digital']}
    seen=set()
    for key,value in mappings.items():
        if key not in ids or value not in ('ignore',*(ANALOG_TARGETS if ids[key]=='analog' else CANONICAL)):
            raise ValueError('Channel meaning does not match this source identity/kind.')
        if value!='ignore' and (ids[key],value) in seen:
            raise ValueError('Assign each explicit channel meaning once; keep other channels separate or ignored.')
        seen.add((ids[key],value))
    return dict(voltage_kv=kv,mappings=dict(sorted(mappings.items())))


def diagnostic_identity(root, revision, filename, options=None):
    source,_=_source(root,revision,filename)
    options=normalise_options(options,source)
    identity=dict(incident_id=revision['incident_id'],revision=revision['number'],file=filename,
                  source_sha256=source['source_sha256'],options=options)
    identity['job_id']=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    return identity


def _prepared(source,item,options):
    out=dict(source)
    out['channels']=[dict(c) for c in source['channels']]
    headers={c['id']:c for c in source.get('header_inventory',[])}
    mapped={c['id']:c.get('selected') or c.get('automatic') or '' for c in item.get('channel_inventory',[])}
    mapped.update(options['mappings'])
    assumptions=[]
    notes=[]
    for c in out['channels']:
        key=c['key']
        h=headers.get(key,{})
        c['meaning']=mapped.get(key) or (c['label'] if c['label'] in ANALOG_TARGETS else '')
        if key in options['mappings']:
            c['frequency_reference']=c['meaning'] in ('VA','VB','VC')
            c['current_reference']=c['meaning'] in ('IA','IB','IC')
        unit=h.get('declared_units','').upper()
        side=h.get('primary_secondary','').upper()
        a,b,primary,secondary=(_number(h.get(k)) for k in ('a','b','primary','secondary'))
        valid_ratio=primary is not None and secondary is not None and primary>0 and secondary>0
        ratio={132:600,220:800}.get(options['voltage_kv'])
        if c['units']=='raw counts' and ratio and not valid_ratio and side=='S' and unit in ('A','KA') and a is not None and b is not None:
            gain=1000 if unit=='KA' else 1
            factor=a*ratio*gain
            if not math.isfinite(factor) or abs(factor)<2.2250738585072014e-308:
                notes.append(key+': CT default could not establish a representable scale; raw counts retained.')
                continue
            values=[None if v is None else (v*a+b)*ratio*gain for v in c['values']]
            if any(v is not None and (not math.isfinite(v) or (v!=0 and abs(v)<2.2250738585072014e-308)) for v in values):
                notes.append(key+': assumed scaling exceeds numeric range; raw counts retained.')
                continue
            c.update(values=values,units='A (assumed CT ratio, unverified)')
            assumptions.append(dict(channel_id=key,ratio=ratio,ratio_text=f'{ratio}/1',voltage_kv=options['voltage_kv'],
                source='user voltage-level default',basis='Missing ratio; known secondary current and CFG a*x+b. No CT/VT/wiring verification.'))
        elif c['units']=='raw counts':
            notes.append(key+': physical scale not available; source gain/offset, units, secondary/primary side and ratio are required. Counts remain analysable.')
    return out,assumptions,notes,mapped


def diagnose_source(root,revision,filename,options=None):
    source,item=_source(root,revision,filename)
    options=normalise_options(options,source)
    prepared,assumptions,notes,mapped=_prepared(source,item,options)
    result=analyse_source(prepared,max_windows=512)
    # Keep compact diagnostics. Native arrays remain on the bounded inspection
    # endpoint; snapshots never carry an unbounded copy of digital/axis arrays.
    result.pop('digital',None)
    result.pop('axis',None)
    for c,original in zip(result['channels'],prepared['channels'],strict=True):
        c.pop('trace',None)
        c.update(id=c['key'],meaning=original.get('meaning',''))
    identity=diagnostic_identity(root,revision,filename,options)
    result.update(identity,time_basis=_axis(source),assumptions=assumptions,scaling_notes=notes,
        digital_evidence=digital_evidence(source,options['mappings']|{k:v for k,v in mapped.items() if k.startswith('D') and k not in options['mappings'] and v in CANONICAL}))
    result['trip'],result['ar']=trip_ar(result['digital_evidence'])
    fits=sum(c['status']=='model_consistent' for w in result['windows'] for c in w['channels'].values())
    total=sum(len(w['channels']) for w in result['windows'])
    result['fit_coverage']=dict(model_consistent=fits,withheld=total-fits,total=total)
    result['methods']={
        'source_models':dict(status='Conditional source models' if fits else 'Not available',
            reason='Actual source-time frequency and stationary fits; every refused window retains its reason. Lower-density/short-support alternatives are not yet independently validated.'),
        'sequence':dict(status='Not available',reason='Requires corresponding phase supports, reviewed phase wiring/polarity and compatible verified scaling.'),
        'rx':dict(status='Not available',reason='Requires corresponding voltage/current supports and reviewed scaling/polarity; ground loops also require residual compensation.'),
        'location':dict(status='Not available',reason='Requires an eligible location method, supplied line length/constants and its terminal/clock/measurement prerequisites. CT assumptions alone cannot establish distance.')}
    result['conclusions']=dict(
        observed=[f"{source['sample_count']} source samples; {len(source['channels'])} analog and {len(source['digital'])} digital channels.",result['trip']['text']],
        supports=[f'{fits} of {total} evaluated channel-windows are model-consistent in export coordinates.',result['ar']['text']],
        cannot_conclude=['Physical fault identity, actual relay operating time, common event/clock/ends and physical location are not established by successful decoding or signal fitting.'],
        needed_next=['Review channel meanings and source scaling; supply breaker/AR settings and pole indications for a cause assessment; supply line facts and method prerequisites for location.'])
    return result
