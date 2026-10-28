"""Sliding source-sample RMS for viewing; independent of phasor eligibility."""
import math


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
    values = channel.get('values', [])
    times = source['axis'].get('elapsed_s', [])
    frequency = source.get('nominal_frequency_hz')
    out = dict(values=[None]*len(values), window_s=None,
               reason='Valid source times and a declared 40..70 Hz nominal frequency are required.',
               basis='Equal-weight sample RMS over a trailing nominal cycle; includes DC/harmonics. Source units, not verified primary quantities.')
    if (not times or len(times) != len(values) or not isinstance(frequency, (int, float))
            or isinstance(frequency, bool) or not 40 <= frequency <= 70):
        return out
    if not all(math.isfinite(t) for t in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
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
