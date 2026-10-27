"""Per-record direct-time diagnostics; independent of terminal clock synchrony."""
import math

import numpy as np

from .nonuniform import fit_source_window, source_frequency, withheld


def _summary(channel):
    values=np.array([np.nan if x is None else x for x in channel['values']],dtype=float)
    finite=np.isfinite(values)
    points=[]
    for group in np.array_split(np.arange(len(values)),min(128,len(values))):
        valid=group[finite[group]]
        if len(valid):
            ids=sorted(set([int(valid[np.argmin(values[valid])]),int(valid[np.argmax(values[valid])])]))
            points.extend([[i,float(values[i])] for i in ids])
    return dict(key=channel['key'],label=channel['label'],units=channel['units'],
        finite_samples=int(sum(finite)),missing_samples=int(sum(~finite)),
        sample_min=float(np.min(values[finite])) if any(finite) else None,
        sample_max=float(np.max(values[finite])) if any(finite) else None,
        trace=points,trace_basis='Sample-index min/max display envelope; not all samples.')


def _stable_fit(t,y,f):
    result=fit_source_window(t,y,f)
    if result['status']!='model_consistent':
        return result
    half=len(t)//2
    parts=[fit_source_window(t[:half],y[:half],f),fit_source_window(t[half:],y[half:],f)]
    if any(p['status']!='model_consistent' for p in parts):
        return withheld('Half-support model unavailable; no stationary measurement.')
    ph=[complex(*p['phasor'])*np.exp(2j*np.pi*f*(result['centre_s']-p['centre_s'])) for p in parts]
    change=float(abs(ph[0]-ph[1])/result['rms'])
    if not math.isfinite(change) or change>.10:
        return withheld('Half-support fundamental changes exceed the stationary-model policy.')
    result['half_support_change']=change
    return result


def analyse_source(observations,*,max_windows=512):
    """Preserve sample visibility even when timing or signal models are unavailable."""
    out=dict(status='sample_only',content_hash=observations.get('content_hash',''),
        parse_status=observations['status'],source_sha256=observations.get('source_sha256',{}),
        station=observations.get('station',''),device=observations.get('device',''),
        channels=[_summary(c) for c in observations['channels']],
        sample_count=observations['sample_count'],issues=list(observations['issues']),
        digital=observations['digital'],axis=observations['axis'],windows=[],
        windows_planned=0,windows_evaluated=0,remaining_windows=0,coverage_complete=False,
        authorizes_location=False,alignment_eligible=False,authorizes_production_dsp=False,
        physical_timing_verified=False,ct_vt_verified=False,
        basis='Export-coordinate signal models, not calibrated phasors or protection verdicts.')
    axis=observations['axis']
    nominal=observations.get('nominal_frequency_hz')
    if axis['status']!='source_time_inspection' or nominal is None or not 40<=nominal<=70:
        out['issues'].append('Timed model unavailable; source sample inspection retained.')
        return out
    if type(max_windows) is not int or not 1<=max_windows<=512:
        out['issues'].append('Unsupported analysis-window budget.')
        return out
    t=np.asarray(axis['elapsed_s'])
    if len(t)<3 or not np.all(np.isfinite(t)) or not 0<t[-1]-t[0]<=3600:
        out['issues'].append('Unsupported declared duration; sample inspection retained.')
        return out
    duration,hop=4/nominal,2/nominal
    planned=max(0,int(np.floor((t[-1]-t[0]-duration)/hop+1e-10))+1)
    out['windows_planned']=planned
    channels=observations['channels']
    arrays={c['key']:np.array([np.nan if v is None else v for v in c['values']]) for c in channels}
    for index in range(min(planned,max_windows)):
        lo=t[0]+index*hop
        hi=lo+duration
        ids=np.flatnonzero((t>=lo)&(t<=hi))
        window=dict(index=index,support_s=[float(lo),float(hi)],sample_count=len(ids),channels={})
        def references(flag,ids=ids):
            selected=[]
            for c in channels:
                values=arrays[c['key']][ids]
                if c.get(flag,False) and c['skew_us']==0 and len(ids) and np.all(np.isfinite(values)):
                    scale=max(float(np.max(abs(values))),1e-100)
                    if np.ptp(values/scale)>1e-6:
                        selected.append(values)
            return selected
        refs=references('frequency_reference')
        freq=source_frequency(t[ids],np.column_stack(refs),nominal) if refs else withheld('No complete explicit voltage reference.')
        basis='phase voltage'
        if freq['status']!='estimated':
            refs=references('current_reference')
            freq=source_frequency(t[ids],np.column_stack(refs),nominal) if refs else freq
            basis='phase current; voltage reference unavailable'
        window['frequency']=freq
        window['frequency_basis']=basis
        for channel in channels:
            key=channel['key']
            if freq['status']!='estimated' or len(ids)<48 or channel['skew_us']!=0:
                fit=withheld('Frequency, complete half-support or declared zero skew unavailable.')
            else:
                fit=_stable_fit(t[ids],arrays[key][ids],freq['frequency_hz'])
            window['channels'][key]=fit
        out['windows'].append(window)
    out.update(status='source_analysis',windows_evaluated=len(out['windows']),
        remaining_windows=planned-len(out['windows']),coverage_complete=planned>0 and planned==len(out['windows']))
    if out['remaining_windows']:
        out['issues'].append('Window budget exhausted; remaining supports have not been analysed.')
    return out
