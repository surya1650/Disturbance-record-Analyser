"""Conservative local stage interiors; separate quality from whole-record flags."""
import numpy as np

from .detect import detect_clipping, detect_saturation
from .window_quality import NAMES, window_transition

POLICY = {'blank_cycles': 1.5, 'end_guard_cycles': .5, 'minimum_window_cycles': 2,
          'maximum_relative_phasor_scatter': .05}


def stage_window(an, stage):
    out = {'status': 'withheld', 'reason': '', 'window_s': None, 'sample_bounds': None,
           'phasor_count': 0, 'policy': dict(POLICY), 'whole_record_saturation': an.saturation.detected,
           'whole_record_clipping': list(an.clipping), 'local_saturation': None,
           'local_clipping': [], 'maximum_relative_scatter': None}
    rec, ps = an.record, an.ps
    if (rec.blocked() or rec.nrates > 1 or not np.isfinite(rec.fs) or not np.isfinite(an.freq) or rec.fs <= 0 or an.freq <= 0 or
            not np.allclose(np.diff(rec.t), 1/rec.fs, rtol=.01, atol=1e-7)):
        out['reason'] = 'Blocked or unsupported acquisition; no stage window authorized.'
        return out
    if not stage['stable'] or not stage['phase_pattern']:
        out['reason'] = 'No stable elevated phase-current interval.'
        return out
    start = max(stage['start_s'], stage['start_boundary_range_s'][1])+POLICY['blank_cycles']/an.freq
    edge = stage['end_boundary_range_s']
    end = min(stage['end_s'], edge[0] if edge else stage['end_s'])-POLICY['end_guard_cycles']/an.freq
    out['window_s'] = [float(start), float(end)]
    if (end-start)*an.freq < POLICY['minimum_window_cycles']:
        out['reason'] = 'Insufficient interior after boundary support, transient blanking and end guard.'
        return out
    ids = ps.window_indices(start, end)
    lo, hi = int(np.searchsorted(rec.t, start)), int(np.searchsorted(rec.t, end, side='right'))
    out.update(sample_bounds=[lo, hi], phasor_count=len(ids))
    if len(ids) < round(rec.fs/an.freq) or any(n not in ps.phasors for n in NAMES):
        out['reason'] = 'Insufficient complete DFT supports or missing phase phasors.'
        return out
    raw = [rec.analog.get(n, np.array([]))[lo:hi] for n in NAMES]
    values = np.array([ps.phasors[n][ids] for n in NAMES])
    if any(len(v) != hi-lo or not np.all(np.isfinite(v)) for v in raw) or not np.all(np.isfinite(values)):
        out['reason'] = 'Nonfinite or missing waveform/phasor support.'
        return out
    sat = detect_saturation(rec.analog, rec.fs, an.freq, lo, hi)
    clip = detect_clipping({k: v[lo:hi] for k, v in rec.raw_analog.items()}, rec.analog_meta)
    center = np.median(values.real, axis=1)+1j*np.median(values.imag, axis=1)
    floor = np.array([max(.2*abs(an.ref.get(n, 0j)), 1e-6) for n in NAMES])
    scatter = np.max(np.percentile(abs(values-center[:, None]), 95, axis=1)/np.maximum(abs(center), floor))
    out.update(local_saturation=sat.detected, local_clipping=clip, maximum_relative_scatter=float(scatter))
    if sat.detected or clip:
        out['reason'] = 'Saturation or clipping within the selected stage interior.'
    elif scatter > POLICY['maximum_relative_phasor_scatter']:
        out['reason'] = 'Phasors are not sufficiently stationary within this stage interior.'
    elif window_transition(an, start, end)['status'] == 'transition detected':
        out['reason'] = 'A further settled-state transition lies inside this candidate stage.'
    else:
        out.update(status='eligible', reason='Guarded local interior passed bounded quality screens; same-stage review is still required.')
    return out
