"""Automatic display intervals from actual-time RMS, never operational windows.

The cycle-block stage screen's 20% baseline / 25% largest-rise policies are
reused as display change thresholds. Six baseline MADs reject observed baseline
variation. A quarter-cycle persistence and two baseline cycles are display
policies, not protection settings or standard accuracy limits. A threshold
crossing's preceding nominal cycle is retained as its boundary support; no
subsample inception, interpolation, physical clearing or clock alignment is
inferred. Operational DSP/window selection and location methods are unchanged.
"""
from bisect import bisect_left
from collections import OrderedDict
from copy import deepcopy
import json
import math
import threading

import numpy as np

from ..dsp.stages import POLICY as STAGE_POLICY
from .source_diagnostics import _prepared, normalise_options
from .source_display import timeline
from .source_events import digital_evidence
from .source_rms import sample_rms
from .source_inspection import _LOCK

_AUTO_LOCK = threading.Lock()

POLICY = dict(baseline_cycles=2, persistence_cycles=.25, noise_mads=6,
              relative_to_baseline=STAGE_POLICY['relative_to_baseline'],
              relative_to_largest_rise=STAGE_POLICY['relative_to_largest_rise'])


def _first_run(mask, times, state, start, duration):
    first = None
    for i in range(start, len(mask)):
        if mask[i] is not None and bool(mask[i]) is state:
            first = i if first is None else first
            if times[i]-times[first] >= duration-1e-12:
                return first
        else:
            first = None
    return None


def _region(times, lo, hi, period):
    return [lo, hi] if 0 <= lo < hi <= len(times) and times[hi-1]-times[lo] >= period-1e-12 else None


def auto_regions(source, item, *, mappings=None, asserted_states=None):
    """Cache bounded display suggestions on the immutable decoded-source LRU."""
    options = normalise_options(dict(mappings={} if mappings is None else mappings,
        asserted_states={} if asserted_states is None else asserted_states), source)
    key = json.dumps([options, item.get('channel_inventory', []), item.get('channel_mapping', {})], sort_keys=True)
    with _AUTO_LOCK:
        cache = source.setdefault('_auto_regions', OrderedDict())
        if key not in cache:
            result = _calculate_regions(source, item, options)
            times = source.get('axis', {}).get('elapsed_s', [])
            result['intervals'] = {kind: dict(start_s=times[bounds[0]],last_s=times[bounds[1]-1],
                samples=bounds) for kind in ('pre','fault','post') if (bounds:=result[kind])}
            cache[key] = result
            while len(cache) > 4:
                cache.popitem(last=False)
        cache.move_to_end(key)
        return deepcopy(cache[key])


def _calculate_regions(source, item, options):
    """Choose conservative observation intervals for the first supported event.

    Missing phases are allowed, ambiguous phases are excluded. Current rise is
    preferred, with voltage drop as a weak-infeed alternative. Restoration of
    that recorded pattern is a display boundary, not proof of CB opening.
    """
    out = dict(version=1, status='unavailable', method='Actual-time one-cycle RMS change screen',
        pre=None, fault=None, post=None, boundaries={}, evidence=[], notes=[], reason='',
        policy=dict(POLICY), authorizes_location=False)
    times = source.get('axis', {}).get('elapsed_s', [])
    n, frequency = source.get('sample_count', len(times)), source.get('nominal_frequency_hz')
    if (not times or n != len(times) or any(type(t) not in (int, float) or not math.isfinite(t) for t in times)
            or any(b <= a for a, b in zip(times, times[1:], strict=False))
            or type(frequency) not in (int, float) or not math.isfinite(frequency) or not 40 <= frequency <= 70):
        out['reason'] = 'Automatic timing needs increasing source times and a declared 40–70 Hz nominal frequency.'
        return out
    period = 1/frequency
    out['timeline'] = {k: v for k, v in timeline(source).items() if k != 'ticks'}
    prepared, _, _, mapped, provenance = _prepared(source, item, options)
    masks = {'I': [], 'V': []}
    baseline_stop = bisect_left(times, times[0]+(1+POLICY['baseline_cycles'])*period)
    for meaning in ('IA', 'IB', 'IC', 'VA', 'VB', 'VC'):
        choices = [c for c in prepared['channels'] if c.get('meaning') == meaning]
        if len(choices) != 1:
            if choices:
                out['notes'].append(meaning+': duplicate identity excluded from automatic timing.')
            continue
        c = choices[0]
        prefix = c.get('units', '').split(' ', 1)[0].upper()
        if (meaning.startswith('I') and prefix in ('V', 'KV') or
                meaning.startswith('V') and prefix in ('A', 'KA')):
            continue
        with _LOCK:
            cached = source.setdefault('_viewer_rms', {})
            if c['key'] not in cached:
                cached[c['key']] = sample_rms(prepared, c)
            rms = cached[c['key']]
        values = rms['values']
        base_indices = [i for i in range(min(n, baseline_stop)) if times[i] >= times[0]+period-1e-12]
        baseline = [values[i] for i in base_indices if values[i] is not None]
        if (baseline_stop >= n or len(baseline) < 4 or
                len(baseline) != len(base_indices) or
                times[min(n-1, baseline_stop-1)]-times[0] < (1+POLICY['baseline_cycles'])*period-period/4):
            continue
        base = float(np.median(baseline))
        noise = float(np.median(np.abs(np.asarray(baseline)-base)))
        delta = [(v-base if meaning.startswith('I') else base-v) if v is not None else None for v in values]
        peak = max((v for v in delta if v is not None), default=0.)
        threshold = max(POLICY['relative_to_baseline']*base,
                        POLICY['relative_to_largest_rise']*peak, POLICY['noise_mads']*noise)
        if peak <= 0 or not math.isfinite(threshold) or peak <= threshold:
            continue
        masks[meaning[0]].append([None if v is None else v > threshold for v in delta])
        out['evidence'].append(dict(id=c['key'], label=c['label'], meaning=meaning,
            mapping_source=provenance.get(c['key'], 'label suggestion'), units=c['units'],
            baseline_rms=base, change_threshold=threshold, baseline_samples=[0, baseline_stop]))

    def combined(group):
        return [True if any(mask[i] is True for mask in group) else
                None if any(mask[i] is None for mask in group) else False for i in range(n)]

    first, mask = None, None
    for kind in ('I', 'V'):
        if not masks[kind]:
            continue
        candidate = combined(masks[kind])
        found = _first_run(candidate, times, True, baseline_stop, period*POLICY['persistence_cycles'])
        if found is not None:
            if any(v is None for v in candidate[baseline_stop:found]):
                out['notes'].append('Unknown RMS support before the change prevents a bounded first-event onset.')
                continue
            first, mask = found, candidate
            out['method'] += ' · '+('current rise' if kind == 'I' else 'voltage drop')
            break
    if first is None:
        # A recorded START can supply a short-capture observation window. Its
        # assertion is labelled as such; it is not renamed physical inception.
        evidence = digital_evidence(source, mapped, limit=16, mapping_sources=provenance,
                                    asserted_states=options.get('asserted_states', {}))
        starts = []
        for c in evidence:
            if 'START' not in c['meanings'] or not c['interpretation_available']:
                continue
            if c['id'] not in options.get('asserted_states', {}) and c['declared_normal_state'] is None:
                continue
            edges = c['rising_edges'] if c['asserted_state'] == 1 else c['falling_edges']
            starts.extend((edge['index'], c) for edge in edges)
        if starts:
            first, signal = min(starts, key=lambda entry: entry[0])
            stop = bisect_left(times, times[first]+3*period)
            out.update(pre=_region(times, 0, first, period), fault=_region(times, first, min(n, stop), period),
                status='partial', method='Recorded START assertion observation window',
                reason='Selected an early observation window after recorded START; physical fault inception and clearing are unknown.')
            out['boundaries']['start'] = dict(index=first, source_s=times[first],
                support_s=[times[max(0, first-1)], times[first]], kind='recorded START assertion')
            out['evidence'].append(dict(id=signal['id'], label=signal['label'],
                assertion_source=signal['assertion_source'], mapping_source=signal['mapping_source']))
        else:
            out['reason'] = 'No sustained current-rise/voltage-drop boundary with a usable baseline or supported START assertion was found. Adjust timings manually if the event is known.'
        return out

    onset_lo = bisect_left(times, times[first]-period)
    out['boundaries']['start'] = dict(index=first, source_s=times[first],
        support_s=[times[onset_lo], times[first]], kind='RMS change support; not physical fault inception')
    out['pre'] = _region(times, 0, onset_lo, period)
    trigger = out['timeline'].get('trigger_offset_s')
    if trigger is not None and times[0] <= trigger < times[baseline_stop]:
        out['pre'] = None
        out['notes'].append('The recorded trigger lies inside the baseline support. A healthy pre-fault interval is not established; the trigger is not treated as physical fault inception.')
    clear = _first_run(mask, times, False, first+1, period*POLICY['persistence_cycles'])
    gap = next((i for i in range(first+1, n) if mask[i] is None), None)
    if gap is not None and (clear is None or gap <= clear):
        out['fault'] = _region(times, first, gap, period)
        out['notes'].append('Missing RMS support interrupts the event; no post-fault interval is inferred across it.')
    elif clear is None:
        out['fault'] = _region(times, first, n, period)
        out['notes'].append('The changed pattern continues to the capture boundary; post-fault values are unavailable.')
    else:
        clear_lo = bisect_left(times, times[clear]-period)
        out['fault'] = _region(times, first, clear_lo, period)
        next_event = _first_run(mask, times, True, clear+1, period*POLICY['persistence_cycles'])
        stop = bisect_left(times, times[next_event]-period) if next_event is not None else n
        out['post'] = _region(times, clear, stop, period)
        out['boundaries']['end'] = dict(index=clear, source_s=times[clear],
            support_s=[times[clear_lo], times[clear]], kind='recorded pattern restoration; not breaker opening')
        if next_event is not None:
            out['notes'].append('A later changed pattern is present. Only the first event is selected; post-fault stops before the next event support.')
    out['status'] = 'selected' if all(out[k] for k in ('pre', 'fault', 'post')) else 'partial'
    out['reason'] = 'Automatic first-event observation intervals selected from sustained RMS changes; review the plotted support if needed.'
    if out['fault'] is None:
        out['notes'].append('The bounded fault interval is too short for a complete one-cycle RMS value.')
    out['notes'].append('Boundary support spans up to one nominal cycle. No CT/VT ratio, clock correction or physical breaker time is inferred.')
    return out
