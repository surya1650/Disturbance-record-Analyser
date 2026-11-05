"""Bounded digital state supports and sampled-window evidence for reader reports."""
import math

from .source_events import digital_evidence

MAX_CHANNELS = 4
MAX_SEGMENTS = 2048


def _segments(states, times, breaks):
    start = None
    for index, state in enumerate(states):
        if start is not None and (state not in (0, 1) or state != states[start] or index in breaks):
            yield dict(from_index=start, to_index=index-1,
                from_s=times[start], to_s=times[index-1], state=states[start])
            start = None
        if start is None and state in (0, 1):
            start = index
    if start is not None:
        yield dict(from_index=start, to_index=len(states)-1,
            from_s=times[start], to_s=times[-1], state=states[start])


def _bounded_segments(states, times, breaks, focus):
    first, event, total = [], [], 0
    for segment in _segments(states, times, breaks):
        total += 1
        if len(first) < MAX_SEGMENTS:
            first.append(segment)
        if (focus and segment['to_s'] >= focus[0] and segment['from_s'] <= focus[1]
                and len(event) < MAX_SEGMENTS//2):
            event.append(segment)
    if total <= MAX_SEGMENTS:
        return first, 0
    chosen = {row['from_index']: row for row in [*first[:MAX_SEGMENTS-len(event)], *event]}
    retained = sorted(chosen.values(), key=lambda row: row['from_index'])
    return retained, total-len(retained)


def _window(states, times, bounds, breaks, asserted):
    empty = dict(status='unavailable', time_range_s=None, indices=None,
        raw_state_at_start=None, asserted_at_start=None, active_during_window=None,
        observed_active_span_s=None, duration_bounds_s=None, observed_high_span_s=None,
        high_duration_bounds_s=None, censored_start=True, censored_end=True,
        gap_count=0, unknown_samples=0,
        reason='No bounded selected/detected during-event sample interval is available.')
    if (not isinstance(bounds, (list, tuple)) or len(bounds) != 2
            or any(type(v) is not int for v in bounds)
            or not 0 <= bounds[0] < bounds[1] <= len(times)):
        return empty
    lo, hi = bounds
    bits = states[lo:hi]
    stable = {0: 0., 1: 0.}
    for i in range(lo+1, hi):
        if i not in breaks and states[i] in (0, 1) and states[i-1] == states[i]:
            stable[states[i]] += times[i]-times[i-1]
    span = times[hi-1]-times[lo]
    unknown = sum(v not in (0, 1) for v in bits)
    gaps = sum(lo < i < hi for i in breaks)
    target = asserted if asserted in (0, 1) else 1
    raw_start = bits[0] if bits[0] in (0, 1) else None
    observed = target in bits
    active = observed if observed or not (unknown or gaps) else None
    high_bounds = [stable[1], max(stable[1], span-stable[0])]
    duration = [stable[target], max(stable[target], span-stable[1-target])]
    reviewed = asserted in (0, 1)
    note = ('Sampled-state duration bracket within the window; transition brackets and missing support limit timing. '
            'It is not a physical relay or breaker operating time.')
    if not reviewed:
        note = 'Asserted-state polarity is unreviewed; high/low observations remain available. '+note
    return dict(status='available', indices=list(bounds), time_range_s=[times[lo], times[hi-1]],
        raw_state_at_start=raw_start,
        asserted_at_start=raw_start == asserted if raw_start is not None and reviewed else None,
        active_during_window=active if reviewed else None,
        observed_active_span_s=stable[target] if reviewed else None,
        duration_bounds_s=duration if reviewed else None,
        observed_high_span_s=stable[1], high_duration_bounds_s=high_bounds,
        censored_start=bits[0] == target or bits[0] not in (0, 1),
        censored_end=bits[-1] == target or bits[-1] not in (0, 1),
        gap_count=gaps, unknown_samples=unknown, reason=note)


def attach_digital_inspection(report, source, mappings, provenance, asserted_states, *, breaks=()):
    """Add exact constant-state supports; endpoints inclusive, transition brackets unknown."""
    times = source.get('axis', {}).get('elapsed_s', [])
    available = (times and all(type(t) in (int, float) and math.isfinite(t) for t in times)
        and all(b > a for a, b in zip(times, times[1:], strict=False)))
    if not available:
        report['digital']['inspection'] = dict(status='unavailable', channels=[],
            reason='Known increasing source sample times are unavailable.', authorizes_location=False)
        return
    evidence = digital_evidence(source, mappings, limit=0,
        mapping_sources=provenance, asserted_states=asserted_states)
    original = {channel['key']: channel for channel in source['digital']}
    def priority(channel):
        names = channel['meanings']
        return (0 if any(name.startswith('TRIP') for name in names) else
                1 if any(name.startswith('CB_OPEN') or name.endswith('POLE_DEAD') for name in names) else
                2 if 'START' in names else 3 if any(name.startswith('AR_') for name in names) else 4 if names else 5)
    selected = sorted(evidence, key=priority)[:MAX_CHANNELS]
    rows = []
    boundary = set(breaks)
    for channel in selected:
        states = original[channel['id']]['states']
        if len(states) != len(times):
            continue
        asserted = asserted_states.get(channel['id'])
        summary = _window(states, times,
            (report.get('region_support', {}).get('fault') or {}).get('indices'), boundary, asserted)
        focus = (report.get('waveform_focus') or {}).get('time_range_s') or summary['time_range_s']
        segments, omitted = _bounded_segments(states, times, boundary, focus)
        rows.append(dict(id=channel['id'], label=channel['label'], meaning=', '.join(channel['meanings']),
            asserted_state=asserted, polarity_label='Explicit asserted-state review' if asserted in (0, 1) else
                'Assertion polarity unreviewed; raw high/low only',
            segments=segments, omitted_segments=omitted, window_summary=summary))
    report['digital']['inspection'] = dict(status='available', channels=rows,
        total_channels=len(source['digital']), omitted_channels=max(0, len(source['digital'])-len(rows)),
        channel_limit=MAX_CHANNELS, max_segments_per_channel=MAX_SEGMENTS,
        selection_policy='Trip, breaker feedback, start and reclose meanings, then source order; bounded display selection.',
        segment_selection='All runs within budget; dense signals retain beginning and event-context runs. Omitted support stays unavailable.',
        endpoint_rule='Segment endpoints are included native observations; transition brackets and gaps between segments are unavailable.',
        duration_basis='Summed stable sampled-state spans and transition/missing-support duration brackets inside the selected window.',
        authorizes_location=False)
