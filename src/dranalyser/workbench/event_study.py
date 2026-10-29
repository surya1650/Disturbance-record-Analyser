"""Explicit event regions and source observations; operational maths stays separate."""
import math
from pathlib import Path

from .source_diagnostics import _prepared, normalise_options
from .source_events import digital_evidence, trip_ar
from .source_inspection import _source, _trace
from .source_rms import sample_rms
from .source_snapshot import line_facts
from .source_regions import auto_regions


def _object(value, allowed, label):
    if not isinstance(value, dict) or set(value)-set(allowed):
        raise ValueError(label+' has unsupported fields.')
    return value


def _text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value)>limit:
        raise ValueError(label+' must be nonempty text, at most '+str(limit)+' characters.')
    return value.strip()


def _unit_quantity(value):
    """Recognize quantity only; this does not convert or verify an electrical scale."""
    prefix=str(value or '').upper().split('(',1)[0].split()
    unit=prefix[0] if prefix else ''
    if unit in ('V','KV','MV','UV'):
        return 'voltage'
    if unit in ('A','KA','MA','UA'):
        return 'current'
    return None


def record_inventory(revision):
    """Frozen scalar inventory, without decoding every record in a large incident."""
    frozen={f['name']:f['sha256'] for f in revision.get('files', [])}
    out=[]
    for item in (revision.get('bundle') or {}).get('files', []):
        if item.get('kind')!='comtrade':
            continue
        names=[item['name']]+([item['data_file']] if item.get('data_file') else [])
        out.append(dict(file=item['name'], station=item.get('station',''), device=item.get('device_id',''),
            sample_count=item.get('samples',0), time_range_s=None,
            source_sha256={Path(n).name:frozen[n] for n in names if n in frozen}))
    return out


def prepare_inputs(root, revision, value):
    """Strictly bind at most two declared ends to frozen decoded source bytes."""
    value=_object(value, {'same_event_confirmed','ends'}, 'Event inputs')
    if type(value.get('same_event_confirmed',False)) is not bool:
        raise ValueError('Same-event confirmation must be true or false.')
    ends=_object(value.get('ends'), {'S','R'}, 'Selected ends')
    if not 1<=len(ends)<=2:
        raise ValueError('Choose one or two recordings explicitly for the event study.')
    prepared={}
    sources={}
    for end, chosen in ends.items():
        chosen=_object(chosen, {'record','substation','pre','fault','post','relay_distance','mappings','asserted_states','timing_mode','timing_evidence'}, end+' inputs')
        record=_text(chosen.get('record'), end+' record', 1000)
        source,item=_source(root, revision, record)
        times=source.get('axis',{}).get('elapsed_s',[])
        if (not times or source.get('sample_count')!=len(times)
                or not all(type(t) in (int,float) and math.isfinite(t) for t in times)
                or any(b<=a for a,b in zip(times,times[1:],strict=False))):
            raise ValueError(record+': known strictly increasing source times are required for event regions.')
        inputs=dict(record=record, substation=_text(chosen.get('substation'), end+' substation',120))
        options=normalise_options(dict(voltage_kv=0,mappings=chosen.get('mappings',{}),
            asserted_states=chosen.get('asserted_states',{})),source)
        inputs.update(mappings=options['mappings'],asserted_states=options.get('asserted_states',{}))
        mode=chosen.get('timing_mode','manual')
        if mode not in ('auto','manual'):
            raise ValueError('Timing selection must be auto or manual.')
        inputs['timing_mode']=mode
        automatic=auto_regions(source,item,mappings=inputs['mappings'],asserted_states=inputs['asserted_states']) if mode=='auto' else None
        inputs['timing_evidence']=automatic if automatic else dict(status='manual',method='Operator-selected sample intervals',authorizes_location=False)
        for field in ('pre','fault','post'):
            region=automatic[field] if automatic else chosen.get(field)
            if region is not None and (not isinstance(region,list) or len(region)!=2
                    or any(type(i) is not int for i in region) or not 0<=region[0]<region[1]<=len(times)):
                raise ValueError(end+' '+field+' interval must be two native indices [start, stop), within this capture.')
            inputs[field]=region
        if inputs['pre'] and inputs['fault'] and inputs['pre'][1]>inputs['fault'][0]:
            raise ValueError(end+' pre-fault interval must finish before the fault interval starts.')
        preceding=inputs['fault'] or inputs['pre']
        if preceding and inputs['post'] and preceding[1]>inputs['post'][0]:
            raise ValueError(end+' post-fault interval must start after the preceding selected interval finishes.')
        reported=chosen.get('relay_distance')
        if reported is not None:
            reported=_object(reported, {'km','reference','evidence'}, 'Relay-reported distance')
            km=reported.get('km')
            if type(km) not in (float,int) or not 0<=km<=1000000 or not math.isfinite(km):
                raise ValueError('Relay-reported distance must be finite km from 0 to 1000000.')
            if reported.get('reference') not in ('S','R'):
                raise ValueError('Relay distance reference must explicitly be S or R.')
            reported=dict(km=km,reference=reported['reference'],evidence=_text(reported.get('evidence'),'Relay distance evidence',1000))
        inputs['relay_distance']=reported
        prepared[end]=inputs
        sources[end]=(source,item)
    if len(ends)==2:
        if value.get('same_event_confirmed') is not True:
            raise ValueError('Confirm both recordings concern the same event before comparing ends.')
        a,b=(sources[k][0] for k in ('S','R'))
        if prepared['S']['record']==prepared['R']['record'] or sorted(a['source_sha256'].values())==sorted(b['source_sha256'].values()):
            raise ValueError('The same capture cannot represent both physical ends.')
        def identity(s):
            return tuple(str(s.get(k) or '').strip().casefold() for k in ('station','device'))
        if all(identity(a)) and identity(a)==identity(b):
            raise ValueError('Both captures declare the same station and relay. Successive captures from one relay are joined at one end, not assigned to opposite ends.')
    return dict(same_event_confirmed=value.get('same_event_confirmed',False),ends=prepared),sources


def _region_rms(values,times,period,region):
    if not region or period is None:
        return None,0
    lo,hi=region
    eligible=[values[i] for i in range(lo,hi) if values[i] is not None and times[i]-period+1e-12>=times[lo]]
    if not eligible:
        return None,0
    eligible.sort()
    a,b=eligible[(len(eligible)-1)//2],eligible[len(eligible)//2]
    return a+(b-a)/2,len(eligible)


def _phase(source,channel,inputs,*,cached_rms=None):
    rms=cached_rms if cached_rms is not None else sample_rms(source,channel)
    times=source['axis']['elapsed_s']
    pre,np=_region_rms(rms['values'],times,rms['window_s'],inputs['pre'])
    fault,nf=_region_rms(rms['values'],times,rms['window_s'],inputs['fault'])
    post,na=_region_rms(rms['values'],times,rms['window_s'],inputs['post'])
    percent=None
    reason=''
    interpretation='Choose pre-fault and fault intervals to compare this phase.'
    if pre is not None and fault is not None:
        if pre>0:
            change=(fault/pre-1)*100
            percent=change if math.isfinite(change) else None
        if percent is None:
            reason='Percentage change is undefined for a zero baseline or unrepresentable ratio.'
        calibrated=channel['units'].split(' ',1)[0] in ('V','A')
        kind=('Voltage' if channel['meaning'].startswith('V') else 'Current') if calibrated else 'Recorded-channel RMS'
        direction='increased' if fault>pre else 'decreased' if fault<pre else 'unchanged'
        interpretation=f'{kind} {direction} between the selected regions; this alone does not establish fault type or breaker operation.'
        if not calibrated:
            interpretation+=' Physical voltage/current interpretation needs reviewed scaling.'
    else:
        reason='Each selected region needs at least one complete known trailing nominal cycle wholly inside its bounds. '+rms['reason']
    value=dict(id=channel['key'],label=channel['label'],meaning=channel['meaning'],units=channel['units'],
        pre_rms=pre,fault_rms=fault,post_rms=post,change_percent=percent,pre_windows=np,fault_windows=nf,post_windows=na,
        interpretation=interpretation,reason=reason)
    trace=dict(id=channel['key'],label=channel['label'],meaning=channel['meaning'],units=channel['units'],
        trace=_trace(channel['values'],times,100),rms_trace=_trace(rms['values'],times,100))
    return value,trace


def _digital(source,mappings,provenance,origin,asserted_states):
    evidence=digital_evidence(source,mappings,limit=16,mapping_sources=provenance,asserted_states=asserted_states)
    events=[]
    total=sum(c['rising_count']+c['falling_count'] for c in evidence)
    insights=[]
    for channel in evidence:
        if channel['first_active_index']==0 and channel['meanings']:
            insights.append(channel['id']+' '+channel['label']+': already active at capture start under the stated polarity; assertion time is unknown.')
        for state,edges in ((1,channel['rising_edges']),(0,channel['falling_edges'])):
            for edge in edges:
                events.append(dict(**edge,id=channel['id'],label=channel['label'],meaning=', '.join(channel['meanings']),
                    kind='asserted' if state==channel['asserted_state'] else 'cleared',
                    asserted_state=channel['asserted_state'],interpretation_available=channel['interpretation_available'],
                    assertion_source=channel['assertion_source'],
                    relative_fault_s=edge['source_s']-origin if origin is not None and edge['source_s'] is not None else None))
    events.sort(key=lambda e:(e['index'],e['id']))
    trip,ar=trip_ar(evidence)
    insights.extend([trip['text'],ar['text'],'Trip and close indications are commands or recorded states; breaker opening requires pole/open feedback. Sample brackets do not establish physical operating times.'])
    return dict(events=events[:128],total_events=total,omitted_events=total-min(128,len(events)),insights=insights[:32])


def _end_report(source,item,inputs):
    prepared,_,scaling,mapped,provenance=_prepared(source,item,dict(voltage_kv=0,mappings=inputs['mappings']))
    times=source['axis']['elapsed_s']
    origin=times[inputs['fault'][0]] if inputs['fault'] else None
    groups=dict(voltage=[],current=[])
    values=[]
    withheld=[]
    headers={h['id']:h for h in source.get('header_inventory',[])}
    insights=list(scaling[:12])
    for meaning in ('VA','VB','VC','IA','IB','IC'):
        found=[c for c in prepared['channels'] if c.get('meaning')==meaning]
        if len(found)!=1:
            insights.append(meaning+': '+('no mapped channel' if not found else 'ambiguous mapping; select one channel in Inputs & help')+'.')
            continue
        channel=found[0]
        declared=headers.get(channel['key'],{}).get('declared_units','')
        expected='voltage' if meaning.startswith('V') else 'current'
        conflict=next((kind for unit in (channel['units'],declared) if (kind:=_unit_quantity(unit)) and kind!=expected),None)
        if conflict:
            reason=meaning+' mapping conflicts with recorded '+conflict+' units; review meaning/scaling.'
            mapping_source=provenance.get(channel['key'],'exact source label')
            withheld.append(dict(id=channel['key'],label=channel['label'],meaning=meaning,units=channel['units'],
                declared_units=declared,mapping_source=mapping_source,reason=reason))
            insights.append(reason+' '+channel['key']+' '+channel['label']+'; units '+channel['units']+
                ('; CFG units '+declared if declared else '')+'; mapping: '+mapping_source+'. Source waveform remains available.')
            continue
        original=next(c for c in source['channels'] if c['key']==found[0]['key'])
        cached=(source.get('_viewer_rms') or {}).get(original['key']) if original['values'] is found[0]['values'] and original['units']==found[0]['units'] else None
        value,trace=_phase(prepared,found[0],inputs,cached_rms=cached)
        value['mapping_source']=provenance.get(found[0]['key'],'exact source label')
        trace['mapping_source']=value['mapping_source']
        values.append(value)
        groups['voltage' if meaning.startswith('V') else 'current'].append(trace)
    return dict(record=inputs['record'],substation=inputs['substation'],sample_count=len(times),
        time_range_s=[times[0],times[-1]],source_sha256=source['source_sha256'],origin_s=origin,
        groups=groups,phase_values=values,withheld_phases=withheld,insights=insights,digital=_digital(source,mapped,provenance,origin,inputs['asserted_states']),
        mappings=inputs['mappings'],asserted_states=inputs['asserted_states'],
        timing_mode=inputs['timing_mode'],timing_evidence=inputs['timing_evidence'],
        pre=inputs['pre'],fault=inputs['fault'],post=inputs['post'],
        time_basis='Source-local seconds; selected fault-region start is a display reference only, not synchronized or detected fault inception.',
        rms_basis='Median of complete trailing one-cycle sample RMS observations wholly within each selected region; includes DC/harmonics. Source units and declared scaling are unverified.')


def build_event_report(root,revision,inputs, *, prepared=None):
    """Compare explicit regions without treating display selections as study evidence."""
    inputs,sources=prepared if prepared is not None else prepare_inputs(root,revision,inputs)
    ends={end:_end_report(*sources[end],chosen) for end,chosen in inputs['ends'].items()}
    facts=line_facts(root,revision)
    existing=revision.get('result') or {}
    used=existing.get('used') or {}
    selected={end:chosen['record'] for end,chosen in inputs['ends'].items()}
    matches=bool(used) and used==selected
    location=facts['location']
    method=existing.get('location_text','').partition(' by ')[2].strip() or None
    km=location.get('km_from_S') if matches and method and location.get('overlay_eligible') is True and facts.get('parameter_status')!='provisional' else None
    reasons=['Display selections and one-cycle RMS do not authorize fault location.',facts['provenance'],
        'A stored operational estimate uses its reviewed mappings and line model; display-only choices do not recompute it.']
    if not matches:
        reasons.append('The selected display records do not match a stored operational end assignment and accepted result.')
    if facts.get('parameter_status')=='provisional':
        reasons.append('Line parameters are provisional; review the line model before using a distance.')
    if km is None:
        reasons.append(location['text'])
    if not method:
        reasons.append('No accepted fault-location method is named for this selection.')
    blocks=[flag[:500] for _,item in sources.values() for flag in item.get('flags',[]) if flag.startswith('[BLOCK')]
    reasons.extend(blocks[:8])
    distance=dict(status='Existing conditional estimate' if km is not None else 'Inputs or eligible study required',
        text=location['text'] if km is not None else 'Run the existing incident study with the reviewed line and physical end assignments to calculate probable fault distance.',
        method=method if km is not None else None,parameter_status=facts.get('parameter_status','Not available'),
        km_from_S=km,reference='S',reason=' '.join(reasons),
        source_records=used,next_action=dict(kind='operational-study',label='Review end assignments and run incident study',
            requirements=['Verified CT/VT ratios and channel meanings','Line section impedances and length','Physical sending/receiving end assignments','Eligible fault and pre-fault observations']))
    reported=[]
    for end,chosen in inputs['ends'].items():
        entry=chosen['relay_distance']
        if entry is None:
            continue
        length=facts['length_km']
        outside=length is not None and entry['km']>length
        converted=None if outside else entry['km'] if entry['reference']=='S' else length-entry['km'] if length is not None else None
        delta=converted-km if converted is not None and km is not None else None
        reported.append(dict(end=end,**entry,reported_from_S_km=converted,delta_to_calculated_km=delta,
            reason='Operator-transcribed relay estimate, not patrol-confirmed distance. '+('Reported distance exceeds the declared line length; no comparison is made.' if outside else 'Receiving-end conversion needs a declared line length.' if converted is None else 'Compared only in the declared S reference.')))
    return dict(incident_id=revision['incident_id'],revision=revision['number'],ends=ends,distance=distance,
        relay_distances=reported,authorizes_location=False,notes=[
            'End names and same-event confirmation are operator declarations. Automatic intervals retain their RMS/indication support; manual intervals remain operator selections. Neither establishes synchronized clocks.',
            'No channel ratios, missing samples or physical breaker operation are inferred. Automatic change boundaries are observation support, not certified fault inception. Raw counts remain raw counts; declared engineering units are not independently verified.',
            'One-cycle RMS is an observation summary. Existing validated incident location methods remain separate; a missing or gated estimate is not replaced with a fabricated distance.'])
