"""Declared DAT-time inspection only; never uniform DSP or clock authorization."""
import math
from numbers import Real

import numpy as np


def _empty():
    return dict(status='withheld', reason='', elapsed_s=[], intervals=[],
        authorizes_dsp=False, authorizes_location=False, alignment_eligible=False,
        recorder_accuracy_verified=False,
        basis='DAT source timestamps as declared; not calibrated time or continuous-acquisition proof')


def _vector(values):
    try:
        a = np.asarray(values)
        if a.ndim != 1 or not 3 <= a.size <= 200000 or a.dtype.kind not in 'iuf':
            return None
        if any(isinstance(v, (bool, np.bool_)) for v in np.asarray(values, dtype=object)):
            return None
        a = a.astype(float)
        return a if np.all(np.isfinite(a)) else None
    except (TypeError, ValueError, OverflowError):
        return None


def source_time_axis(numbers, stamps, *, nrates, timemult):
    """Preserve explicit nrates=0 source coordinates without fitting/resampling."""
    out = _empty()
    try:
        multiplier_ok = (isinstance(timemult, Real) and not isinstance(timemult, (bool, np.bool_))
                         and math.isfinite(timemult) and timemult > 0)
        scale = float(timemult)*1e-6 if multiplier_ok else 0
    except (OverflowError, ValueError):
        scale = 0
    if type(nrates) is not int or nrates != 0 or not math.isfinite(scale) or scale <= 0:
        out['reason'] = 'Require explicit nrates=0 and a finite representable positive multiplier.'
        return out
    nums, raw = _vector(numbers), _vector(stamps)
    if nums is None or raw is None or nums.size != raw.size:
        out['reason'] = 'Require equal finite numeric one-dimensional source arrays,3..200000 samples.'
        return out
    if (np.any(nums < 0) or np.any(nums > 2**53-1) or np.any(nums != np.floor(nums))
            or np.any(np.diff(nums) != 1) or np.any(raw < 0) or np.any(raw > 2**53-1)):
        out['reason'] = 'Unsupported counter range or nonconsecutive/integral sample numbers.'
        return out
    delta = np.diff(raw)
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        elapsed = (raw-raw[0])*scale
        periods = delta*scale
    if (np.any(delta <= 0) or not np.all(np.isfinite(elapsed))
            or not np.all(np.isfinite(periods)) or np.any(np.diff(elapsed) <= 0) or np.any(periods <= 0)):
        out['reason'] = 'Source times must increase without overflow/underflow/collapsed coordinates.'
        return out
    starts = np.r_[0, np.flatnonzero(np.diff(delta) != 0)+1]
    ends = np.r_[starts[1:], len(delta)]
    runs = [dict(first_from_index=int(lo), last_to_index=int(hi), interval_count=int(hi-lo),
                 raw_period=float(delta[lo]), declared_period_s=float(periods[lo]))
            for lo, hi in zip(starts, ends, strict=True)]
    out.update(status='source_time_inspection', reason='Declared source coordinates only; all analytical gates remain external.',
               elapsed_s=elapsed.tolist(), minimum_interval_s=float(np.min(periods)),
               maximum_interval_s=float(np.max(periods)), raw_period_runs=runs)
    return out


def digital_source_intervals(numbers, stamps, states, *, nrates, timemult):
    """Sample-bracket source edges; never label their span a relay operating time."""
    out = source_time_axis(numbers, stamps, nrates=nrates, timemult=timemult)
    if out['status'] == 'withheld':
        return out
    bits = _vector(states)
    if bits is None or len(bits) != len(out['elapsed_s']) or np.any((bits != 0) & (bits != 1)):
        invalid = _empty()
        invalid['reason'] = 'Digital source states must be finite binary values matching the source axis.'
        return invalid
    time = out['elapsed_s']
    edges = np.flatnonzero(np.diff(bits) != 0)+1
    onset = None
    active = bool(bits[0])
    intervals = []

    def segment(start, end):
        known = start is not None and end is not None
        return dict(start_index=start, end_index=end,
            start_source_s=time[start] if start is not None else None,
            end_source_s=time[end] if end is not None else None,
            source_span_s=time[end]-time[start] if known else None,
            duration_sample_bracket_s=[max(0.0, time[end-1]-time[start]),
                                      time[end]-time[start-1]] if known else None,
            onset_unknown=start is None, ending_unknown=end is None)

    for index in edges:
        index = int(index)
        if bits[index] == 1:
            onset, active = index, True
        else:
            intervals.append(segment(onset, index))
            active, onset = False, None
    if active:
        intervals.append(segment(onset, None))
    out['intervals'] = intervals
    out['transitions'] = [dict(index=int(i), state=int(bits[i]), source_s=time[i],
                               sample_bracket_s=[time[i-1],time[i]]) for i in edges]
    return out
