"""Bounded display-window selection for conditional source-model projections.

This consumes existing observation intervals and fitted quantities. It does not
plan or shorten DSP windows, infer a loop, or authorize a physical location.
"""
import copy
import math


def _support(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)
            or value[1] <= value[0]):
        return None
    return list(value)


def _fault_support(source, regions):
    bounds = regions.get('fault')
    times = source.get('axis', {}).get('elapsed_s', [])
    if (not isinstance(bounds, (list, tuple)) or len(bounds) != 2
            or any(type(i) is not int for i in bounds)
            or not 0 <= bounds[0] < bounds[1] <= len(times)):
        return None, None
    support = _support([times[bounds[0]], times[bounds[1]-1]])
    return (support, list(bounds)) if support else (None, None)


def _inside(support, fault):
    return bool(support and fault and support[0] >= fault[0]-1e-12 and support[1] <= fault[1]+1e-12)


def _crosses_break(source, support):
    axis = source.get('axis', {})
    times = axis.get('elapsed_s', [])
    boundaries = [*source.get('break_indices', []), *axis.get('break_indices', [])]
    # A declared break precedes its indexed sample. Supports starting within
    # that missing bracket are also unavailable, even if their first included
    # sample is already on the other side of it.
    return any(type(index) is int and 0 < index < len(times)
        and support[0] < times[index] and support[1] > times[index-1]
        for index in boundaries)


def _unavailable(reason, selection):
    selection.update(status='unavailable', reason=reason)
    return dict(status='Not available', reason=reason, distance_km=None,
        eligible_overlay=False, authorizes_location=False, window_selection=selection)


def _selected(row, selection):
    return dict(copy.deepcopy(row['projection']), window_index=row['index'],
        support_s=copy.deepcopy(row['support_s']), authorizes_location=False, window_selection=selection)


def select_projection_window(source, item, options, derived):
    """Use only an existing eligible support wholly within the detected event.

    Nearest interval centre, then lowest window index, is a deterministic display
    policy. Distance, amplitude and the rest of the capture never rank candidates.
    Manual choices remain explicit overrides with their detected-interval warning.
    """
    # source_regions prepares channels through source_diagnostics; import only
    # when called, after the diagnostics module has finished loading.
    from .source_regions import auto_regions
    regions = auto_regions(source, item, mappings=options.get('mappings', {}),
        asserted_states=options.get('asserted_states', {}))
    fault, bounds = _fault_support(source, regions)
    manual = options.get('projection_window')
    selection = dict(mode='manual' if manual is not None else 'automatic', status='unavailable',
        reason='', fault_support_s=fault, fault_sample_indices=bounds,
        detected_region_status=regions.get('status'), detected_region_method=regions.get('method'),
        candidate_count=0, warning='', authorizes_location=False,
        policy='Existing eligible support nearest the detected interval centre; ties use the window index. Display policy only.')
    if manual is not None:
        selection['requested_window_index'] = manual
        row = next((w for w in derived if w['index'] == manual), None)
        if row is None:
            return _unavailable('The manually selected source window is not available in this analysis.', selection)
        selection['requested_support_s'] = copy.deepcopy(row.get('support_s'))
        support = _support(row.get('support_s'))
        if support is None:
            return _unavailable('The manually selected source window has no complete source-time support.', selection)
        if _crosses_break(source, support):
            return _unavailable('The manually selected source window crosses a declared source break; '
                'a manual override cannot restore missing support.', selection)
        selection.update(status='selected', reason='Advanced manual source-window override; projection assumptions and fit gates still apply.')
        if fault is None:
            selection['warning'] = 'No bounded fault observation interval was detected; this manual support is not confirmed as during the event.'
        elif not _inside(support, fault):
            selection['warning'] = 'Manual support is outside or extends beyond the detected fault observation interval.'
        return _selected(row, selection)
    loop = options.get('fault_loop', '')
    if loop not in ('AB', 'BC', 'CA'):
        return _unavailable('Choose an explicit phase-phase fault-loop assumption; ground loops require a separate compensation contract.', selection)
    if fault is None:
        reason = (regions.get('reason') or 'No bounded fault observation interval was detected.').replace(
            ' Adjust timings manually if the event is known.', '')
        return _unavailable('Automatic source-window selection is not available: '+
            reason, selection)
    contained = [w for w in derived if _inside(_support(w.get('support_s')), fault)]
    if not contained:
        return _unavailable('No complete evaluated source-model window lies inside the detected fault observation interval. '+
            'Existing native supports are not shortened or extended beyond that interval.', selection)
    candidates = [w for w in contained
        if w['projection'].get('status') in ('Conditional model projection', 'Outside supplied line')
        and type(w['projection'].get('distance_km')) in (int, float)
        and math.isfinite(w['projection']['distance_km']) and not _crosses_break(source, w['support_s'])]
    selection['candidate_count'] = len(candidates)
    if not candidates:
        reasons = list(dict.fromkeys(w['projection'].get('reason') for w in contained if w['projection'].get('reason')))
        return _unavailable('No eligible projection in the detected fault observation interval: '+
            (' '.join(reasons[:3]) or 'Existing source-model support is unavailable or crosses a declared source break.'), selection)
    centre = (fault[0]+fault[1])/2
    chosen = min(candidates, key=lambda w: (abs((w['support_s'][0]+w['support_s'][1])/2-centre), w['index']))
    selection.update(status='selected', reason='Automatically selected an existing eligible source-model support wholly inside '+
        'the detected fault observation interval, nearest its centre. This is an assumption-dependent display projection.')
    return _selected(chosen, selection)
