"""Bounded onset-shape correlation, advisory only; never a clock correction.

Uses fundamental magnitudes, not AC phase or E5's modulo-cycle angle. Thresholds
are project screening policy, not standard limits or calibrated uncertainty.
"""
from __future__ import annotations

import numpy as np

CHANNELS = ('IA', 'IB', 'IC', 'VA', 'VB', 'VC')
POLICY = {'minimum_score': 0.95, 'score_band': 0.01, 'minimum_channels': 2,
          'minimum_channel_score': 0.90, 'minimum_relative_change': 0.15,
          'maximum_peak_width_cycles': 0.5, 'search_half_width_cycles': 0.25,
          'template_before_cycles': 1.0, 'template_after_cycles': 0.5}


def onset_profile(an):
    """Keep only a short initial segment before any recorded trip edge.

    Multi-rate/gapped acquisition and flagged distortion are not resampled into
    apparently reliable timing. No stage after a trip is associated here.
    """
    rec = an.record
    out = {'reason': '', 'channels': {}, 't': np.array([]), 'onset': None, 'freq': an.freq}
    if an.inception is None:
        out['reason'] = 'detected inception unavailable'
    elif rec.fs <= 0 or rec.nrates > 1 or rec.n < 4 or not np.allclose(np.diff(rec.t), 1/rec.fs, rtol=.01, atol=1e-7):
        out['reason'] = 'multi-rate or irregular sample grid; correlation unsupported'
    elif rec.blocked() or an.saturation.detected or an.clipping:
        out['reason'] = 'blocked, saturated or clipped record; correlation withheld'
    elif not np.isfinite(an.freq) or an.freq <= 0:
        out['reason'] = 'invalid nominal frequency'
    else:
        out['onset'] = float(an.inception.t_refined)
        t = an.ps.t - out['onset']
        # Include every raw trip-like edge only as a conservative stop boundary;
        # canonical operation interpretation remains in the evidence layer.
        trips = [rec.first_assert(n) for n in rec.digital if 'TRIP' in n.upper()]
        trips = [v-out['onset'] for v in trips if v is not None and v > out['onset']]
        stop = min(trips, default=float('inf'))
        if _changing_phases(an, t, stop):
            out['reason'] = 'changing phase-current pattern before trip; stage association needs review'
            return out
        mask = (np.arange(t.size) >= an.ps.valid_from) & (t < stop) & (np.abs(t) <= 3/an.freq)
        out['t'] = t[mask]
        out['channels'] = {n: np.abs(an.ps.phasors[n][mask]) for n in CHANNELS if n in an.ps.phasors}
    return out


def _changing_phases(an, t, stop):
    """Conservative screen, not a complete evolving-fault stage detector."""
    names = ('IA', 'IB', 'IC')
    if not all(n in an.ps.phasors for n in names):
        return False
    cycle = 1/an.freq
    patterns = []
    # Let the inception DFT transition settle. Compare complete later cycles,
    # ending before trip so pole opening is not called a new fault stage.
    end = min(stop, float(t[-1]), 10*cycle)
    for start in np.arange(2*cycle, end-cycle, cycle):
        mask = (t >= start) & (t < start+cycle)
        if mask.sum() < 4:
            continue
        delta = np.array([abs(float(np.median(np.abs(an.ps.phasors[n][mask])))-abs(an.ref.get(n, 0j))) for n in names])
        if np.all(np.isfinite(delta)) and np.max(delta) > 0:
            patterns.append(tuple(delta > .25*np.max(delta)))
    return len(set(patterns)) > 1


def correlate_onsets(left, right):
    """Compare fixed-duration onset templates with equal overlap at every lag.

    Returned lag maps right local time = left local time + lag. Near-peak lag
    range measures score sensitivity only; it is NOT a confidence interval.
    Even a unique candidate cannot establish that two records are the same event.
    """
    out = {'status': 'unavailable', 'reason': '', 'method': 'fundamental-magnitude onset correlation',
           'lag_ms': None, 'lag_range_ms': None, 'score': None, 'channels': [], 'grid_ms': None,
           'policy': dict(POLICY), 'applied': False,
           'basis': 'right local time = left local time + lag; local timelines retained',
           'caveat': 'Candidate shape similarity is not verified event identity, clock accuracy or cross-end event order.'}
    for p in (left, right):
        if p['reason']:
            out['reason'] = p['reason']
            return out
    if abs(left['freq']-right['freq']) > 1:
        out['reason'] = 'frequency mismatch'
        return out
    cycle = 1/min(left['freq'], right['freq'])
    if min(len(left['t']), len(right['t'])) < 4:
        out['reason'] = 'insufficient initial-segment samples'
        return out
    step = max(float(np.max(np.diff(p['t']))) for p in (left, right))
    step = max(step, .0005)
    count = int(np.floor(cycle*POLICY['search_half_width_cycles']/step+1e-9))
    if count < 2:
        out['reason'] = 'sampling too coarse for lag search'
        return out
    lags = np.arange(-count, count+1)*step
    grid = np.arange(-cycle*POLICY['template_before_cycles'], cycle*POLICY['template_after_cycles']+step/2, step)
    out.update(search_half_width_ms=float(lags[-1]*1000),
               left_window_local_s=[float(left['onset']+grid[i]) for i in (0, -1)],
               right_search_window_local_s=[float(right['onset']+grid[i]+lags[i]) for i in (0, -1)])
    # Fixed support prevents a high score obtained by discarding unmatched data.
    if (left['t'][0] > grid[0] or left['t'][-1] < grid[-1] or
            right['t'][0] > grid[0]+lags[0] or right['t'][-1] < grid[-1]+lags[-1]):
        out['reason'] = 'insufficient pre/post-inception coverage before trip for full lag search'
        return out
    xs, ys, names = [], [], []
    for name in CHANNELS:
        if name not in left['channels'] or name not in right['channels']:
            continue
        x = np.interp(grid, left['t'], left['channels'][name])
        y = np.array([np.interp(grid+lag, right['t'], right['channels'][name]) for lag in lags])
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            continue
        # Require a substantial changing envelope at both ends, not numerical
        # ripple in an otherwise steady sinusoid.
        if (np.ptp(x) < POLICY['minimum_relative_change']*max(np.max(np.abs(x)), 1e-12) or
                np.min(np.ptp(y, axis=1)) < POLICY['minimum_relative_change']*max(np.max(np.abs(y)), 1e-12)):
            continue
        x = x-x.mean()
        y = y-y.mean(axis=1, keepdims=True)
        xs.append(x/np.linalg.norm(x))
        ys.append(y/np.linalg.norm(y, axis=1, keepdims=True))
        names.append(name)
    out.update(channels=names, grid_ms=step*1000)
    if len(names) < POLICY['minimum_channels']:
        out['reason'] = 'fewer than two changing common phase channels'
        return out
    per_channel = np.array([y @ x for x, y in zip(xs, ys, strict=True)])
    scores = per_channel.mean(axis=0)
    best = int(np.argmax(scores))
    out['score'] = float(scores[best])
    near = np.flatnonzero(scores >= scores[best]-POLICY['score_band'])
    if scores[best] < POLICY['minimum_score'] or np.min(per_channel[:, best]) < POLICY['minimum_channel_score']:
        out.update(status='inconsistent', reason='onset shapes disagree across available phases')
    elif best in (0, len(lags)-1) or near[0] == 0 or near[-1] == len(lags)-1:
        out.update(status='ambiguous', reason='peak reaches the lag-search boundary')
    elif np.any(np.diff(near) > 1) or lags[near[-1]]-lags[near[0]] > cycle*POLICY['maximum_peak_width_cycles']:
        out.update(status='ambiguous', reason='multiple or broad correlation peaks')
    else:
        offset = right['onset']-left['onset']
        out.update(status='candidate', reason='initial onset shapes compatible; event/stage identity needs review',
                   lag_ms=float((offset+lags[best])*1000),
                   lag_range_ms=[float((offset+lags[i])*1000) for i in (near[0], near[-1])])
    return out
