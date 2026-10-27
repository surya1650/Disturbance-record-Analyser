"""Independent supported source analysis with explicit, unverified assumptions."""
from bisect import bisect_left, bisect_right
import copy
import hashlib
import json
import math

from ..comtrade.source_observations import _number
from .source_models import analyse_models
from ..rules.signals import CANONICAL
from .channel_mapping import ANALOG_TARGETS
from .source_inspection import _source, _axis
from .source_events import digital_evidence, trip_ar
from .source_snapshot import compose_snapshot
from .source_quantities import compose_source_quantities
from .source_lines import normalise_model, resolve_line


def normalise_options(options, source):
    options={} if options is None else options
    if not isinstance(options,dict) or set(options)-{'voltage_kv','mappings','line_id','line_model','fault_loop','projection_window','asserted_states'}:
        raise ValueError('Unsupported source-analysis choice; use declared scaling, meanings, line/fault-loop and digital-state inputs only.')
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
    out=dict(voltage_kv=kv,mappings=dict(sorted(mappings.items())))
    identifier=options.get('line_id','')
    if not isinstance(identifier,str) or len(identifier)>200:
        raise ValueError('Choose a configured line identifier of at most200 characters.')
    model=options.get('line_model',{})
    if not isinstance(model,dict):
        raise ValueError('Custom line model must be a mapping of explicit declared fields.')
    if identifier and model:
        raise ValueError('Choose one configured line or one custom declared model, not both.')
    if identifier:
        out['line_id']=identifier
    if model:
        out['line_model']=normalise_model(model)
    loop=options.get('fault_loop','')
    if loop not in ('','AB','BC','CA','AG','BG','CG'):
        raise ValueError('Choose an explicit recognised phase loop; no fault loop is inferred.')
    if loop:
        out['fault_loop']=loop
    window=options.get('projection_window')
    if window is not None:
        if type(window) is not int or not 0<=window<512:
            raise ValueError('Projection window must be an available nonnegative window index below512.')
        out['projection_window']=window
    states=options.get('asserted_states',{})
    if not isinstance(states,dict) or any(key not in ids or ids[key]!='digital' or type(value) is not int or value not in (0,1) for key,value in states.items()):
        raise ValueError('Asserted digital states require an existing digital source ID and explicit0or1.')
    if states:
        out['asserted_states']=dict(sorted(states.items()))
    return out


def diagnostic_identity(root, revision, filename, options=None, *, registry=None, resolved_line=None):
    source,item=_source(root,revision,filename)
    options=normalise_options(options,source)
    stored=revision.get('result') or {}
    metadata=revision.get('metadata') or {}
    context=dict(inventory=item.get('channel_inventory',[]),reviewed_mapping=item.get('channel_mapping',{}),
        record_hash=item.get('content_hash'),terminal_end=item.get('terminal_end'),role=item.get('role'),
        state=revision.get('state'),assignment=(metadata.get('assignments') or {}).get(filename),
        line_id=(revision.get('bundle') or {}).get('line_id'),
        operational={key:stored.get(key) for key in ('line_snapshot','parameter_status','location_text','used')})
    context_hash=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
    identity=dict(incident_id=revision['incident_id'],revision=revision['number'],file=filename,
                  source_sha256=source['source_sha256'],options=options,revision_context_sha256=context_hash,line_sha256=(resolved_line if resolved_line is not None else resolve_line(root,revision,options,registry))['sha256'])
    identity['job_id']=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    return identity


def _effective_meanings(item,options):
    meanings={}
    provenance={}
    for channel in item.get('channel_inventory',[]):
        key=channel['id']
        reviewed=channel.get('reviewed') is True
        target=(channel.get('selected') or 'ignore') if reviewed else (channel.get('selected') or channel.get('automatic') or '')
        if target:
            meanings[key]=target
            provenance[key]='reviewed revision choice' if reviewed else 'label suggestion'
    for kind in ('analog','digital'):
        for key,target in (item.get('channel_mapping') or {}).get(kind,{}).items():
            meanings[key]=target
            provenance[key]='reviewed revision choice'
    for key,target in options['mappings'].items():
        meanings[key]=target
        provenance[key]='source-analysis choice'
    return meanings,provenance


def _prepared(source,item,options):
    out=dict(source)
    out['channels']=[dict(c) for c in source['channels']]
    headers={c['id']:c for c in source.get('header_inventory',[])}
    mapped,mapping_sources=_effective_meanings(item,options)
    assumptions=[]
    notes=[]
    for c in out['channels']:
        key=c['key']
        h=headers.get(key,{})
        c['meaning']=mapped.get(key) or (c['label'] if c['label'] in ANALOG_TARGETS else '')
        if key in mapped:
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
            products=[None if v is None else v*a for v in c['values']]
            if any(v is not None and v!=0 and (p==0 or abs(p)<2.2250738585072014e-308)
                   for v,p in zip(c['values'],products,strict=True)):
                notes.append(key+': assumed gain multiplication underflows; raw observations retained.')
                continue
            values=[None if p is None else (p+b)*ratio*gain for p in products]
            if any(v is not None and (not math.isfinite(v) or (v!=0 and abs(v)<2.2250738585072014e-308)) for v in values):
                notes.append(key+': assumed scaling exceeds numeric range; raw counts retained.')
                continue
            c.update(values=values,units='A (assumed CT ratio, unverified)')
            assumptions.append(dict(channel_id=key,ratio=ratio,ratio_text=f'{ratio}/1',voltage_kv=options['voltage_kv'],
                source='user voltage-level default',basis='Missing ratio; known secondary current and CFG a*x+b. No CT/VT/wiring verification.'))
        elif c['units']=='raw counts':
            notes.append(key+': physical scale not available; source gain/offset, units, secondary/primary side and ratio are required. Counts remain analysable.')
    return out,assumptions,notes,mapped,mapping_sources


def diagnose_source(root,revision,filename,options=None, *, registry=None, model_cache=None):
    source,item=_source(root,revision,filename)
    options=normalise_options(options,source)
    line=copy.deepcopy(resolve_line(root,revision,options,registry))
    prepared,assumptions,notes,mapped,mapping_sources=_prepared(source,item,options)
    result=model_cache.analyse(prepared,options['voltage_kv']) if model_cache is not None else analyse_models(prepared)
    # Keep compact diagnostics. Native arrays remain on the bounded inspection
    # endpoint; snapshots never carry an unbounded copy of digital/axis arrays.
    times=source['axis'].get('elapsed_s',[])
    for window in result['windows']:
        window['start_index']=bisect_left(times,window['support_s'][0])
        window['stop_index']=bisect_right(times,window['support_s'][1])
    result.pop('digital',None)
    result.pop('axis',None)
    for c,original in zip(result['channels'],prepared['channels'],strict=True):
        c.pop('trace',None)
        c.update(id=c['key'],meaning=original.get('meaning',''))
    identity=diagnostic_identity(root,revision,filename,options,registry=registry,resolved_line=line)
    result.update(identity,time_basis=_axis(source),assumptions=assumptions,scaling_notes=notes,
        digital_evidence=digital_evidence(source,{k:v for k,v in mapped.items() if k.startswith('D') and v in (*CANONICAL,'ignore')},
            mapping_sources=mapping_sources,asserted_states=options.get('asserted_states',{})))
    result['trip'],result['ar']=trip_ar(result['digital_evidence'])
    fits=sum(c['status']=='model_consistent' for w in result['windows'] for c in w['channels'].values())
    total=sum(len(w['channels']) for w in result['windows'])
    result['fit_coverage']=dict(model_consistent=fits,withheld=total-fits,total=total)
    model_reason='Actual source-time frequency and stationary fits; each refused window retains its reason.'
    if not fits:
        if not result['windows_planned']:
            model_reason=('No complete four-cycle model support fits this capture.' if source['axis']['status']=='source_time_inspection'
                          else 'Source timing is unavailable: '+source['axis'].get('reason','inspect sample indices.'))
        else:
            reasons=list(dict.fromkeys(c.get('reason','') for w in result['windows'] for c in w['channels'].values() if c.get('reason')))
            model_reason='No supported signal fits: '+' '.join(reasons[:3])
    active=[c for c in result['digital_evidence'] if c['active_samples']]
    observed=[f"{c['id']} {c['label']} ({', '.join(c['meanings']) or 'meaning unassigned'}): {c['active_samples']} observations at interpreted state {c['asserted_state']} ({c['assertion_source']}), {c['unknown_samples']} unknown; first observed active at sample {c['first_active_index']}." for c in active[:12]]
    if len(active)>12:
        observed.append(f'{len(active)-12} additional active channels are listed in detailed source evidence.')
    ranges=[]
    for channel in result['channels']:
        rms=[w['channels'][channel['id']]['rms'] for w in result['windows'] if w['channels'][channel['id']]['status']=='model_consistent']
        if rms:
            ranges.append(f"{channel['id']} {channel['label']}: conditional RMS {min(rms):.6g} to {max(rms):.6g} {channel['units']} across {len(rms)} supported windows.")
    result['methods']={
        'source_models':dict(status='Conditional source models' if fits else 'Not available',
            reason=model_reason+' Lower-density/short-support alternatives are not yet independently validated.'),
        'sequence':dict(status='Not available',reason='Requires corresponding phase supports, reviewed phase wiring/polarity and compatible verified scaling.'),
        'rx':dict(status='Not available',reason='Requires corresponding voltage/current supports and reviewed scaling/polarity; ground loops also require residual compensation.'),
        'location':dict(status='Not available',reason='Requires an eligible location method, supplied line length/constants and its terminal/clock/measurement prerequisites. CT assumptions alone cannot establish distance.')}
    result['conclusions']=dict(
        observed=[f"{source['sample_count']} source samples; {len(source['channels'])} analog and {len(source['digital'])} digital channels.",result['trip']['text']]+observed,
        supports=[f'{fits} of {total} evaluated channel-windows are model-consistent in export coordinates.',result['ar']['text']]+ranges,
        cannot_conclude=['Physical fault identity, actual relay operating time, common event/clock/ends and physical location are not established by successful decoding or signal fitting.'],
        needed_next=['Review channel meanings and source scaling; supply breaker/AR settings and pole indications for a cause assessment; supply line facts and method prerequisites for location.'])
    result['derived_quantities']=compose_source_quantities(result['channels'],result['windows'],line,options.get('fault_loop',''))
    derived=result['derived_quantities']['windows']
    sequences=sum(row['sequence'][kind]['status']=='Conditional source quantity' for row in derived for kind in ('voltage','current'))
    loops=sum(loop['status']=='Conditional source quantity' for row in derived for loop in row['loops'].values())
    result['methods']['sequence']=dict(status='Conditional source quantities' if sequences else 'Not available',
        reason=f'{sequences} corresponding window/quantity sets. Requires unique phase meanings, V/A source scaling and corresponding supported fits; phase wiring and physical scaling remain unverified.')
    result['methods']['rx']=dict(status='Conditional source quantities' if loops else 'Not available',
        reason=f'{loops} phase-phase loop windows. Corresponding supported voltage/current fits and non-cancelled loops only; no ground compensation, physical fault or location is inferred.')
    selected=next((w for w in result['derived_quantities']['windows'] if w['index']==options.get('projection_window')),None)
    result['selected_projection']=dict(selected['projection'],window_index=selected['index'],support_s=selected['support_s']) if selected else dict(status='Not available',reason='Choose a supported source window for the selected line/fault-loop model.',distance_km=None,eligible_overlay=False,authorizes_location=False)
    result['methods']['location']=dict(status=result['selected_projection']['status'],reason=result['selected_projection'].get('reason') or result['selected_projection'].get('basis',''))
    result['snapshot']=compose_snapshot(root,revision,filename,result,registry=registry,resolved_line=line)
    return result
