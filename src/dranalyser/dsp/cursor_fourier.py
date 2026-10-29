"""One-cycle cursor Fourier observations, separate from operational estimators.

PROJECT_CONTEXT section 2.5 requires explicit source limitations, not repaired input.
This display operator fits x(t)=d+a*cos(w*(t-t_cursor))+b*sin(w*(t-t_cursor))
on the actual samples in (t_cursor-1/f,t_cursor]. Its RMS complex coefficient is
P=(a-j*b)/sqrt(2), so x=d+sqrt(2)*Re(P*exp(j*w*(t-t_cursor))). The intercept is
eliminated by centering both the harmonic basis and observations before a rank-
checked least-squares solve. On a uniformly sampled integral nominal cycle this
is the one-cycle DFT coefficient; actual-time LS avoids false orthogonality on
nonuniform/noninteger grids. It is not an FFT interpolation or frequency tracker.

A complete source support, >=4 observations (one residual degree of freedom for
three coefficients), a sub-half-cycle maximum step and no reported/acquisition
gaps are display policies. Four samples do not establish anti-alias protection.
4096 samples cap cursor work; the existing eight-minimum-period display gap policy
is retained. Neither is a standards-derived accuracy or relay-operation threshold.
DC, harmonics and transitions remain visible through total RMS/DC/residual. No
stationarity pass or fault-location authority is conferred; existing operational
and four-cycle models retain their own unchanged eligibility requirements.
"""
from bisect import bisect_right
from dataclasses import dataclass
import math
from numbers import Real

import numpy as np

from .fundamental import RANK_TOLERANCE

BOUNDARY_TOLERANCE_S = 1e-12  # Numerical endpoint convention, not clock alignment.
MAX_WINDOW_SAMPLES = 4096
METHOD = 'One-cycle actual-time fundamental Fourier projection with DC term'
BASIS = ('Trailing nominal-cycle equal-weight source-sample observation; frequency is declared, '
         'not measured. Source units/scaling and anti-alias provenance remain unverified. '
         'DC/transients/harmonics can bias a short-support fundamental; inspect residual and waveform. '
         'Not an operational fault-location phasor.')


def _number(value):
    if not isinstance(value, Real) or isinstance(value, (bool, np.bool_)):
        return None
    try:
        return float(value)
    except (OverflowError, ValueError):
        return None


@dataclass(frozen=True, init=False)
class PreparedTimeline:
    """Immutable, validated source coordinates; construct once per frozen source.

    The constructor performs the same checks as a raw-timeline cursor call.
    No unchecked coordinates/derived minimum step can be passed to its initializer.
    Keeping the validated tuple makes subsequent cursor work O(log N + window),
    without rescanning the entire capture or trusting a supplied validation flag.
    """
    coordinates: tuple
    minimum_step_s: float | None
    reason: str

    def __init__(self, times):
        coordinates = tuple(_number(value) for value in times)
        reason, minimum = '', None
        if not coordinates:
            reason = 'Source-time coordinates are unavailable; the sample cursor has no timed cycle.'
        elif any(value is None or not math.isfinite(value) for value in coordinates):
            reason = 'Finite monotone source-time coordinates are required.'
        elif any(b <= a for a, b in zip(coordinates, coordinates[1:], strict=False)):
            reason = 'Finite strictly increasing source-time coordinates are required.'
        elif len(coordinates) > 1:
            minimum = min(b-a for a, b in zip(coordinates, coordinates[1:], strict=False))
        object.__setattr__(self, 'coordinates', coordinates)
        object.__setattr__(self, 'minimum_step_s', minimum)
        object.__setattr__(self, 'reason', reason)


def _missing(reason):
    return dict(status='unavailable', reason=reason, rms=None, fundamental_rms=None,
                total_rms=None, phasor=None, dc=None, angle_deg=None,
                relative_residual=None, condition=None, authorizes_location=False)


def _channel(values, lo, hi, basis, means, condition):
    raw = [_number(v) for v in values[lo:hi]]
    if len(raw) != hi-lo or any(v is None or not math.isfinite(v) for v in raw):
        return _missing('Missing/nonfinite observations occur inside this trailing cycle.')
    scale = max(map(abs, raw), default=0.)
    normal = np.asarray(raw, dtype=float)/(scale or 1.)
    average = float(np.mean(normal))
    centered = normal-average
    coefficients, _, rank, _ = np.linalg.lstsq(basis, centered, rcond=RANK_TOLERANCE*max(basis.shape))
    if rank != 2 or not np.all(np.isfinite(coefficients)):
        return _missing('The one-cycle harmonic basis is numerically rank deficient.')
    real = float(coefficients[0])/math.sqrt(2)*scale
    imag = -float(coefficients[1])/math.sqrt(2)*scale
    magnitude = math.hypot(real, imag)
    dc = (average-float(np.dot(coefficients, means)))*scale
    total = math.sqrt(float(np.mean(normal*normal)))*scale
    residual = centered-basis@coefficients
    denominator = float(np.linalg.norm(centered))
    relative = float(np.linalg.norm(residual))/denominator if denominator else 0.
    if not all(math.isfinite(v) for v in (real, imag, magnitude, dc, total, relative)):
        return _missing('The one-cycle measurement exceeds representable numerical range.')
    return dict(status='observed', reason='', rms=magnitude, fundamental_rms=magnitude,
                total_rms=total, phasor=[real, imag], dc=dc,
                angle_deg=math.degrees(math.atan2(imag, real)) if magnitude else None,
                relative_residual=relative, condition=condition, method=METHOD,
                authorizes_location=False,
                quality_note='Finite one-cycle projection; a low residual does not verify physical wiring, '
                             'scaling, anti-aliasing, stationarity or fault-location eligibility.')


def cursor_fourier(times, values_by_id, frequency_hz, index, *, break_indices=()):
    """Project all channels on the same trailing support, in their supplied units.

    `times` is raw coordinates or a PreparedTimeline validated once and reused.
    `values_by_id` is a mapping of source ID to real sample arrays. Values are
    never imputed and source arrays remain unchanged. Phase is referenced to the
    cursor source coordinate; all returned coefficients share that reference.
    """
    ids = list(values_by_id)
    result = dict(index=index, frequency_hz=frequency_hz, window=None, channels={},
                  method=METHOD, basis=BASIS, authorizes_location=False)

    def unavailable(reason):
        result['channels'] = {identity: _missing(reason) for identity in ids}
        result['reason'] = reason
        return result

    frequency = _number(frequency_hz)
    if frequency is None or not math.isfinite(frequency) or not 40 <= frequency <= 70:
        return unavailable('A declared finite nominal frequency from 40 to 70 Hz is required.')
    timeline = times if isinstance(times, PreparedTimeline) else PreparedTimeline(times)
    if timeline.reason:
        return unavailable(timeline.reason)
    coordinates = timeline.coordinates
    n = len(coordinates)
    if type(index) is not int or not 0 <= index < n:
        raise ValueError('Cursor index must select an existing zero-based source sample.')
    period, end = 1/frequency, coordinates[index]
    start = end-period
    if start < coordinates[0]-BOUNDARY_TOLERANCE_S:
        return unavailable('A complete trailing nominal cycle is not yet available at this cursor.')
    lo = bisect_right(coordinates, start+BOUNDARY_TOLERANCE_S, 0, index+1)
    hi = index+1
    result['window'] = dict(start_index=lo, stop_index=hi, start_s=coordinates[lo] if lo < hi else None,
                            end_s=end, nominal_start_s=start, reference_s=end,
                            interval='(cursor-one nominal cycle, cursor]')
    if not 4 <= hi-lo <= MAX_WINDOW_SAMPLES:
        return unavailable('Use 4 to 4096 source observations inside a complete trailing nominal cycle.')
    relevant = [coordinates[i]-coordinates[i-1] for i in range(max(1, lo), index+1)]
    if (any(lo <= b <= index for b in break_indices) or not relevant
            or max(relevant) > timeline.minimum_step_s*8 or max(relevant)*frequency >= .5):
        return unavailable('A source gap, break or insufficient phase sampling crosses this trailing cycle.')
    phase = 2*math.pi*frequency*(np.asarray(coordinates[lo:hi])-end)
    harmonic = np.column_stack((np.cos(phase), np.sin(phase)))
    means = np.mean(harmonic, axis=0)
    basis = harmonic-means
    singular = np.linalg.svd(basis, compute_uv=False)
    if (len(singular) < 2 or singular[1] <= RANK_TOLERANCE*max(basis.shape)*singular[0]):
        return unavailable('The one-cycle harmonic basis is numerically rank deficient.')
    condition = float(singular[0]/singular[1])
    for identity, values in values_by_id.items():
        result['channels'][identity] = (_channel(values, lo, hi, basis, means, condition)
                                       if len(values) == n else _missing('Channel samples and source times differ in length.'))
    result['reason'] = ''
    return result
