"""Sliding source-sample RMS for viewing; independent of phasor eligibility."""
import math
from numbers import Real
import threading

_TIMING_LOCK = threading.Lock()


def _finite_number(value):
    if not isinstance(value, Real) or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _combine(a, b):
    scale = max(a[0], b[0])
    return (scale, a[1]*(a[0]/scale)**2+b[1]*(b[0]/scale)**2) if scale else (0., 0.)


class _Squares:
    """Two-stack rolling aggregate avoids subtraction/cancellation at clearing."""
    def __init__(self):
        self.front, self.back = [], []

    def push(self, value):
        aggregate = _combine(self.back[-1][1] if self.back else (0., 0.), (abs(value), 1.))
        self.back.append((value, aggregate))

    def pop(self):
        if not self.front:
            while self.back:
                value = self.back.pop()[0]
                aggregate = _combine(self.front[-1][1] if self.front else (0., 0.), (abs(value), 1.))
                self.front.append((value, aggregate))
        self.front.pop()

    def rms(self, count):
        scale, squares = _combine(self.front[-1][1] if self.front else (0., 0.),
                                 self.back[-1][1] if self.back else (0., 0.))
        return scale*min(1., math.sqrt(squares/count))


def sample_rms(source, channel):
    """RMS of samples in (t-one nominal cycle,t], not a continuous-time integral.

    Includes DC/harmonics. Missing observations, timing gaps and incomplete leading
    supports remain unavailable. No resampling, CT/VT inference or phasor gating.
    """
    values = [_finite_number(value) for value in channel.get('values', [])]
    times = [_finite_number(value) for value in source['axis'].get('elapsed_s', [])]
    frequency = _finite_number(source.get('nominal_frequency_hz'))
    out = dict(values=[None]*len(values), window_s=None,
               reason='Valid source times and a declared 40..70 Hz nominal frequency are required.',
               basis='Equal-weight sample RMS over a trailing nominal cycle; includes DC/harmonics. Source units, not verified primary quantities.')
    if not times or len(times) != len(values) or frequency is None or not 40 <= frequency <= 70:
        return out
    if any(t is None for t in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
        return out
    period = 1/frequency
    gap_limit = min((b-a for a, b in zip(times, times[1:], strict=False)), default=period)*8
    queue, lo, missing, gaps = _Squares(), 0, 0, [0]
    boundaries = set(source.get('break_indices', []))
    out.update(window_s=period, reason='A complete trailing cycle of known samples without source-time gaps is required.')
    for i, value in enumerate(values):
        known = value is not None and math.isfinite(value)
        queue.push(value if known else 0.)
        missing += not known
        gaps.append(gaps[-1]+int(i in boundaries or (i > 0 and times[i]-times[i-1] > gap_limit)))
        boundary = times[i]-period
        while lo <= i and times[lo] <= boundary+1e-12:
            old = values[lo]
            missing -= old is None or not math.isfinite(old)
            queue.pop()
            lo += 1
        count = i-lo+1
        if (boundary+1e-12 >= times[0] and count >= 2 and not missing
                and gaps[i+1] == gaps[lo+1] and times[lo]-boundary <= gap_limit
                and not (lo and (lo in boundaries or times[lo]-times[lo-1] > gap_limit))):
            out['values'][i] = queue.rms(count)
    return out


def cursor_measurements(source, channel_ids, index):
    """Bounded source adapter for independent one-cycle cursor observations."""
    from ..dsp.cursor_fourier import PreparedTimeline, cursor_fourier
    if (not isinstance(channel_ids, list) or not 1 <= len(channel_ids) <= 64
            or any(not isinstance(identity, str) for identity in channel_ids)
            or len(set(channel_ids)) != len(channel_ids)):
        raise ValueError('Choose 1 to 64 distinct analog source IDs.')
    channels = {c['key']: c for c in source.get('channels', [])}
    if any(identity not in channels for identity in channel_ids):
        raise ValueError('A cursor measurement channel is not in this analog source inventory.')
    sample_count = source.get('sample_count', len(channels[channel_ids[0]]['values']))
    if type(index) is not int or not 0 <= index < sample_count:
        raise ValueError('Cursor index must select an existing zero-based source sample.')
    times = source['axis'].get('elapsed_s', [])
    # Only immutable decoded source objects use this cache. Its lifetime/budget
    # follows source_inspection's two-source LRU; nothing is retained globally.
    # Identity checks also permit replacing a timeline in independent test sources.
    with _TIMING_LOCK:
        cached = source.get('_cursor_timing')
        if cached is None or cached[0] is not times:
            cached = (times, PreparedTimeline(times))
            source['_cursor_timing'] = cached
    measured = cursor_fourier(cached[1],
        {identity: channels[identity]['values'] for identity in channel_ids},
        source.get('nominal_frequency_hz'), index, break_indices=source.get('break_indices', []))
    for identity, result in measured['channels'].items():
        result.update(id=identity, label=channels[identity].get('label', identity),
                      units=channels[identity].get('units', 'raw counts'))
    return measured
