"""Offline necessary conditions for scalar negative-sequence observability."""
from collections.abc import Mapping
from numbers import Integral

import numpy as np

from ..dsp.window_quality import NAMES, window_transition

POLICY = dict(negative_sequence_fraction=.01, minimum_current_primary_a=1e-6,
              scope='Necessary measured conditions only; no total error bound or field/location authority.')
FAULTS = ('AG', 'BG', 'CG', 'AB', 'BC', 'CA', 'ABG', 'BCG', 'CAG')
STREAMS = (*NAMES, 'I1', 'I2', 'V2')


def _terminal(ti, end):
    out = dict(status='withheld', reason='')

    def refuse(reason):
        return dict(out, reason=reason)

    an, rec = ti.analysed, ti.analysed.record
    if (ti.end != end or rec.terminal_end != end or
            isinstance(ti.polarity, (bool, np.bool_)) or
            not isinstance(ti.polarity, (int, np.integer)) or ti.polarity not in (-1, 1)):
        return refuse('Terminal identity or polarity is unsupported.')
    if rec.blocked() or rec.nrates not in (0, 1):
        return refuse('Blocked or multi-rate acquisition.')
    if (an.saturation.detected is not False or
            not isinstance(an.clipping, (list, tuple)) or an.clipping):
        return refuse('Detected/unknown saturation or clipping; downweighting cannot establish observability.')
    if (not np.all(np.isfinite([rec.fs, an.freq])) or not 0 < an.freq < rec.fs/2 or
            rec.t.ndim != 1 or not np.isrealobj(rec.t) or rec.n < 2 or not np.all(np.isfinite(rec.t)) or
            not np.all(np.diff(rec.t) > 0) or
            not np.allclose(np.diff(rec.t), 1/rec.fs, rtol=.01, atol=1e-7)):
        return refuse('Unsupported local sample grid or frequency.')
    if (any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Integral)
            for v in (an.ps.n_window, an.ps.valid_from)) or
            not 2 <= an.ps.n_window <= rec.n or not an.ps.n_window-1 <= an.ps.valid_from < rec.n or
            np.shape(an.ps.t) != (rec.n,) or not np.isrealobj(an.ps.t) or
            not np.array_equal(an.ps.t, rec.t) or an.ps.fs != rec.fs or an.ps.freq != an.freq or
            an.window.mode not in ('full', 'half') or
            not np.all(np.isfinite([an.window.t_start, an.window.t_end])) or
            an.window.t_end <= an.window.t_start):
        return refuse('Unsupported phasor kernel or analysis window.')
    for name in NAMES:
        meta = rec.analog_meta.get(name)
        if (name not in rec.analog or np.shape(rec.analog[name]) != (rec.n,) or meta is None or
                meta.normalised is not True or not np.all(np.isfinite([meta.primary, meta.secondary])) or
                min(meta.primary, meta.secondary) <= 0):
            return refuse('Complete normalized primary phase channels and ratio metadata required.')
    if any(name not in an.ps.phasors or np.shape(an.ps.phasors[name]) != (rec.n,) for name in STREAMS):
        return refuse('Missing or inconsistent phase/sequence streams.')
    ids = an.indices()
    if len(ids) < 2 or np.min(ids) < an.ps.valid_from or np.max(ids) >= rec.n:
        return refuse('At least two complete local phasor supports required.')
    values = np.array([an.ps.phasors[name][ids] for name in STREAMS])
    if not np.all(np.isfinite(values)):
        return refuse('Nonfinite phase/sequence observation within the complete selected window.')
    if window_transition(an)['status'] == 'transition detected':
        return refuse('Detected transition; a scalar window must not mix settled states.')
    with np.errstate(over='ignore', invalid='ignore'):
        i1 = float(np.median(abs(an.ps.phasors['I1'][ids])))
        minimum = float(np.min(abs(an.ps.phasors['I2'][ids])))
        floor = max(POLICY['negative_sequence_fraction']*i1, POLICY['minimum_current_primary_a'])
    if not np.all(np.isfinite([i1, minimum, floor])):
        return refuse('Unrepresentable sequence magnitudes.')
    out.update(support_count=int(len(ids)), reference_i1_primary_a=i1,
               minimum_i2_primary_a=minimum, required_i2_primary_a=floor)
    if minimum < floor:
        return refuse('At least one selected observation has insufficient negative sequence.')
    return dict(out, status='candidate_pass', reason='Necessary local conditions met; measurement errors remain unbounded.')


def scalar_observability(terminals, *, fault):
    """Assess actual measured S/R analyses, without estimating truth or location."""
    out = dict(status='withheld', authorizes_location=False, policy=dict(POLICY), reason='', terminals={})
    if not isinstance(fault, str) or fault not in FAULTS:
        return dict(out, reason='Known unbalanced measured fault required; no positive-sequence substitute studied.')
    if not isinstance(terminals, Mapping) or set(terminals) != {'S', 'R'}:
        return dict(out, reason='Exactly two S/R terminal analyses required.')
    for end in ('S', 'R'):
        try:
            row = _terminal(terminals[end], end)
        except (AttributeError, TypeError, ValueError, IndexError, OverflowError):
            row = dict(status='withheld', reason='Malformed or unavailable measured terminal evidence.')
        out['terminals'][end] = row
    if any(row['status'] != 'candidate_pass' for row in out['terminals'].values()):
        return dict(out, reason='At least one terminal failed the necessary-condition screen.')
    return dict(out, status='candidate_pass', reason='Both necessary screens passed; no gain/alias/CT/clock/error guarantee.')
