"""Local phase-current pattern intervals, advisory and separate from DSP windows.

Cycle blocks of existing fundamental magnitudes screen elevated phases against
the pre-inception reference. These are neither physical fault classifications nor
proof of clearing. Short runs and DFT transition support remain uncertain.
"""
from __future__ import annotations

import numpy as np

POLICY = {'baseline_cycles': 2, 'minimum_run_cycles': 2, 'relative_to_baseline': .20,
          'relative_to_largest_rise': .25, 'current_floor_a': 1e-6, 'maximum_intervals': 512}


def phase_stages(an):
    rec, ps = an.record, an.ps
    out = {'version': 1, 'status': 'unavailable', 'reason': '', 'intervals': [],
           'policy': dict(POLICY), 'method': 'cycle-block median fundamental current rise',
           'record_hash': rec.content_hash, 'channels': [], 'quality_reasons': [],
           'applied_to_analysis': False,
           'caveat': 'Phase-current patterns are advisory. No elevated current does not prove clearing; '
                     'short stages, weak infeed, changing infeed and faults without magnitude rise may be missed. '
                     'Boundary ranges describe sample/DFT support, not calibrated physical-inception uncertainty.'}
    names = ['I'+p for p in 'ABC']
    freq = getattr(an, 'freq', rec.line_freq)
    if (not np.isfinite(freq) or freq <= 0 or not np.isfinite(rec.fs) or rec.fs <= 0 or
            rec.n < 4 or rec.nrates > 1 or not np.all(np.isfinite(rec.t)) or
            not np.allclose(np.diff(rec.t), 1/rec.fs, rtol=.01, atol=1e-7)):
        out['reason'] = 'Uniform finite single-rate acquisition is required.'
        return out
    if an.inception is None or not np.isfinite(an.inception.t_refined):
        out['reason'] = 'Detected inception unavailable; initial stage and baseline cannot be established.'
        return out
    if any(k not in ps.phasors or k not in getattr(an, 'ref', {}) for k in names):
        out['reason'] = 'All three phase-current phasors and pre-inception references are required.'
        return out
    n = max(1, int(round(rec.fs/freq)))
    onset = float(an.inception.t_refined)
    first = int(np.searchsorted(rec.t, onset))
    if first < POLICY['baseline_cycles']*n or first >= rec.n:
        out['reason'] = 'Insufficient pre-inception capture for stage baseline.'
        return out
    base = np.array([abs(an.ref[k]) for k in names])
    values = np.array([np.abs(ps.phasors[k]) for k in names])
    if values.shape != (3, rec.n) or not np.all(np.isfinite(base)):
        out['reason'] = 'Invalid phase-current reference or phasor coverage.'
        return out
    out['channels'] = [{'channel': k, 'source_channel': rec.analog_meta[k].raw_id if k in rec.analog_meta else k,
                        'baseline_fundamental_a': float(base[i])} for i, k in enumerate(names)]
    if rec.blocked() or an.saturation.detected or an.clipping:
        out['quality_reasons'].append('Blocked, saturated or clipped input; stage association withheld.')
    valid = max(getattr(ps, 'valid_from', 0), first)
    runs = []
    for lo in range(valid, rec.n, n):
        hi = min(lo+n, rec.n)
        block = values[:, lo:hi]
        pattern = None
        if hi-lo == n and np.all(np.isfinite(block)):
            rise = np.maximum(np.median(block, axis=1)-base, 0)
            threshold = max(POLICY['current_floor_a'], POLICY['relative_to_baseline']*float(max(base)),
                            POLICY['relative_to_largest_rise']*float(max(rise)))
            pattern = ''.join(p for p, v in zip('ABC', rise, strict=True) if v > threshold)
        if runs and runs[-1]['pattern'] == pattern:
            runs[-1]['hi'] = hi
            runs[-1]['blocks'] += 1
        else:
            runs.append({'lo': lo, 'hi': hi, 'blocks': 1, 'pattern': pattern})
        if len(runs) > POLICY['maximum_intervals']:
            out['reason'] = 'Stage interval limit exceeded; no partial association inventory published.'
            return out
    history = False
    previous_pattern = None
    dft = max(1, getattr(ps, 'n_window', n))
    for i, run in enumerate(runs):
        lo, hi, pattern = run['lo'], run['hi'], run['pattern']
        stable = pattern is not None and run['blocks'] >= POLICY['minimum_run_cycles']
        kind = 'uncertain transition'
        if stable and pattern:
            kind = 'initial candidate' if not history else (
                'renewed current candidate' if previous_pattern == '' else 'evolving candidate')
            history = True
        elif stable:
            kind = 'no elevated phase current'
        start, end = float(rec.t[lo]), float(rec.t[hi]) if hi < rec.n else float(rec.t[-1])
        # First DFT after a change includes earlier samples; keep this support
        # range visible instead of claiming a precise physical edge.
        support = [float(rec.t[max(0, lo-dft-n+1)]), float(rec.t[min(rec.n-1, lo+n-1)])]
        out['intervals'].append({'id': f'stage-{i+1}', 'kind': kind, 'phase_pattern': pattern,
                                 'stable': stable, 'start_s': start, 'end_s': end,
                                 'sample_start': lo, 'sample_stop': hi, 'blocks': run['blocks'],
                                 'start_boundary_range_s': support, 'end_boundary_range_s': None,
                                 'onset_unknown': i == 0, 'continues_at_capture_end': hi == rec.n,
                                 'eligible_for_estimation': False})
        previous_pattern = pattern if stable else None
    for left, right in zip(out['intervals'], out['intervals'][1:], strict=False):
        left['end_boundary_range_s'] = right['start_boundary_range_s']
    out.update(status='observed', reason='Local observation intervals only; all physical stage identities require review.')
    return out
