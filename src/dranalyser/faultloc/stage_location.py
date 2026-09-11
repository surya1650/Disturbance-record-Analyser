"""E5 on independently guarded, reviewed local stage interiors. No clock shift."""
import numpy as np

from ..dsp.stage_windows import stage_window
from .estimators import e5_roots, e5_unsynchronised
from .model_domain import scalar_model_reasons


def stage_e5(line, s, r, stage_s, stage_r, polarity_s=1, polarity_r=1):
    windows = {'S': stage_window(s, stage_s), 'R': stage_window(r, stage_r)}
    out = {'status': 'withheld', 'method': 'E5', 'm': None, 'km_from_S': None,
           'reason': '', 'windows': windows, 'diagnostics': {}, 'clock_shift_applied': False,
           'caveats': ['Reviewed same-stage, stationary negative-sequence windows are required.',
                       'Relative-position sample pairing is not timestamp synchronization.',
                       'No blended incident distance, tower clamp or calibrated confidence interval is produced.']}
    domain_reasons = scalar_model_reasons(line)
    if domain_reasons:
        out['reason'] = ' '.join(domain_reasons)
        return out
    if any(w['status'] != 'eligible' for w in windows.values()):
        out['reason'] = 'At least one local stage interior fails quality or window prerequisites.'
        return out
    if not np.isfinite(line.z1) or abs(line.z1) == 0 or polarity_s not in (-1, 1) or polarity_r not in (-1, 1):
        out['reason'] = 'Invalid line impedance or explicitly declared current polarity.'
        return out
    indices = [an.ps.window_indices(*windows[end]['window_s']) for end, an in [('S', s), ('R', r)]]
    count = min(24, *(len(i) for i in indices))
    picks = [ids[np.linspace(0, len(ids)-1, count).round().astype(int)] for ids in indices]
    quantities = []
    for an, ids, polarity in [(s, picks[0], polarity_s), (r, picks[1], polarity_r)]:
        if any(n not in an.ps.phasors for n in ('V2', 'I2', 'I1')):
            out['reason'] = 'Sequence phasors unavailable.'
            return out
        i2, i1 = an.ps.phasors['I2'][ids], an.ps.phasors['I1'][ids]
        if np.median(abs(i2)) < max(.01*np.median(abs(i1)), 1e-6):
            out['reason'] = 'Insufficient negative sequence; balanced/weak-sequence stage path withheld.'
            return out
        quantities.extend([an.ps.phasors['V2'][ids], i2*polarity])
    if not np.all(np.isfinite(quantities)):
        out['reason'] = 'Nonfinite sequence phasors.'
        return out
    # The legacy solver's phase-stability tiebreak can be ambiguous on a
    # steady stage. Do not choose between two distinct in-line roots here.
    for values in zip(*quantities, strict=True):
        roots, _, _ = e5_roots(*values, line.z1)
        inside = sorted(v for v in roots if 0 <= v <= 1)
        if len(inside) > 1 and inside[-1]-inside[0] > 1e-4:
            out['reason'] = 'Multiple distinct in-line E5 roots; stage location remains ambiguous.'
            return out
    estimate = e5_unsynchronised(*quantities, line.z1)
    out['diagnostics'] = estimate.diagnostics
    if not estimate.ok or not np.isfinite(estimate.m):
        out['reason'] = estimate.reason
    elif not 0 <= estimate.m <= 1:
        out['reason'] = 'E5 result is outside the protected line; no distance or tower clamping.'
    elif (not np.isfinite(estimate.residual) or estimate.residual > .05 or
          not np.isfinite(estimate.diagnostics.get('delta_std_deg', float('inf'))) or
          estimate.diagnostics.get('delta_std_deg', float('inf')) > 5):
        out['reason'] = 'E5 residual or recovered phase stability fails the bounded stage screen.'
    else:
        out.update(status='located', m=estimate.m, km_from_S=line.m_to_km(estimate.m),
                   reason='E5 from independently guarded local windows of the reviewed stage.')
    return out
