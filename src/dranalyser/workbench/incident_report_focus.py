"""Bounded source-native event views for a frozen reader report, never DSP input."""
from bisect import bisect_left, bisect_right
import math

MAX_POINTS = 2048
_BINS = 400


def _points(values, times, lo, hi, breaks):
    """Keep native observations; dense views retain bucket extrema and gap blanks."""
    boundaries = {i for i in breaks if lo < i < hi}
    if hi-lo+len(boundaries) <= MAX_POINTS:
        points = []
        for index in range(lo, hi):
            if index in boundaries:
                points.append([index, times[index], None])
            points.append([index, times[index], values[index]])
        return points, 'native samples'
    width = max(1, math.ceil((hi-lo)/_BINS))
    points = []
    ordered = sorted(boundaries)
    for start in range(lo, hi, width):
        stop = min(hi, start+width)
        if start in boundaries:
            points.append([start, times[start], None])
        if (any(values[i] is None for i in range(start, stop))
                or bisect_left(ordered, stop) > bisect_right(ordered, start)):
            points.append([start, times[start], None])
            continue
        indices = sorted({start, stop-1, min(range(start, stop), key=values.__getitem__),
                          max(range(start, stop), key=values.__getitem__)})
        points.extend([i, times[i], values[i]] for i in indices)
    return points, 'retained sample envelope'


def attach_waveform_focus(report, prepared, *, breaks=()):
    """Add a display-only interval around the selected fault, retaining full traces."""
    frequency = prepared.get('nominal_frequency_hz')
    fault = (report.get('region_support') or {}).get('fault') or {}
    bounds = fault.get('time_range_s')
    unavailable = dict(status='unavailable', reason='', max_points_per_channel=MAX_POINTS,
                       authorizes_location=False, changes_measurement_windows=False)
    if (type(frequency) not in (int, float) or not math.isfinite(frequency)
            or not 40 <= frequency <= 70):
        unavailable['reason'] = 'A declared 40–70 Hz nominal frequency is required for two-cycle display context; no frequency is assumed.'
        report['waveform_focus'] = unavailable
        return
    if (not isinstance(bounds, (list, tuple)) or len(bounds) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in bounds)
            or bounds[1] < bounds[0]):
        unavailable['reason'] = 'A bounded during-event observation interval is unavailable; the full capture remains the display.'
        report['waveform_focus'] = unavailable
        return
    times = prepared['axis']['elapsed_s']
    if not times:
        unavailable['reason'] = 'Known source-local sample times are unavailable.'
        report['waveform_focus'] = unavailable
        return
    context = 2/frequency
    requested = [max(times[0], bounds[0]-context), min(times[-1], bounds[1]+context)]
    lo, hi = bisect_left(times, requested[0]-1e-12), bisect_right(times, requested[1]+1e-12)
    if hi-lo < 2:
        unavailable['reason'] = 'The source has fewer than two observations inside the event display context.'
        report['waveform_focus'] = unavailable
        return
    channels = {channel['key']: channel for channel in prepared['channels']}
    policy = 'native samples'
    for group in report.get('groups', {}).values():
        for channel in group:
            native = channels.get(channel['id'])
            if native is None:
                continue
            channel['focus_trace'], retained = _points(native['values'], times, lo, hi, breaks)
            channel['focus_trace_policy'] = retained
            if retained != 'native samples':
                policy = retained
    report['waveform_focus'] = dict(status='available', time_range_s=[times[lo], times[hi-1]],
        requested_time_range_s=requested, native_indices=[lo, hi], sample_count=hi-lo,
        context_cycles=2, context_s=context, nominal_frequency_hz=frequency,
        basis='Detected/selected fault interval with two cycles of context; display only.',
        trace_policy=policy, max_points_per_channel=MAX_POINTS,
        reason='Stored points retain actual source indices, times and sample values; no interpolation or RMS-window change.',
        authorizes_location=False, changes_measurement_windows=False)
