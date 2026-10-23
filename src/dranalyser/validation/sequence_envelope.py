"""Independent passive sequence branches and descriptive numerical experiments.

The prescribed negative-sequence fault-node voltage is a controlled network
excitation, not a complete phase-fault or instrument-transformer model.
"""
import cmath
import math
from collections import Counter
from itertools import product

import numpy as np

from ..faultloc.estimators import e5_unsynchronised

INTERVAL_ROUNDOFF_PU = 32*np.finfo(float).eps


def sequence_case(m, source_ratio, rotation):
    """Terminal phasors from branch Ohm laws, with zero sequence-source EMFs."""
    if (not all(math.isfinite(v) for v in (m, source_ratio, rotation)) or
            not 0 <= m <= 1 or source_ratio <= 0):
        raise ValueError('Finite in-line location, positive source ratio and rotation required.')
    z, zs, zr, vf = 3+40j, 4+12j, source_ratio*(9+20j), 100+40j
    is_, ir = -vf/(zs+m*z), -vf/(zr+(1-m)*z)
    turn = cmath.exp(1j*rotation)
    return {'quantities': (-zs*is_, is_, -zr*ir*turn, ir*turn), 'z1': z,
            'true_m': m, 'fault_voltage': vf}


def summarize(cases):
    """Refusals stay in planned denominators; errors condition on located cases."""
    located = [r for r in cases if r['located']]
    errors = [r['error_pct'] for r in located]
    intervals = [r['interval_contains_truth'] for r in located if r['interval_contains_truth'] is not None]
    return {'planned': len(cases), 'located': len(located), 'refused': len(cases)-len(located),
            'located_fraction': len(located)/len(cases) if cases else None,
            'mae_pct': float(np.mean(errors)) if errors else None,
            'p95_error_pct': float(np.percentile(errors, 95)) if errors else None,
            'max_error_pct': max(errors) if errors else None,
            'within_half_percent_all_planned_fraction': sum(e <= .5 for e in errors)/len(cases) if cases else None,
            'interval_cases': len(intervals),
            'diagnostic_interval_contains_truth_fraction': sum(intervals)/len(intervals) if intervals else None,
            'refusal_reasons': dict(Counter(r['reason'] for r in cases if not r['located']))}


def run_envelope(seed=854, repetitions=20):
    """Fixed scenario grid; independent complex Gaussian measurement perturbations.

    Noise RMS is relative to the stronger terminal quantity for each V/I pair.
    Thus a weak remote current is not granted an unrealistically tiny noise floor.
    No noisy-case acceptance threshold or calibrated confidence is asserted.
    """
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or not 1 <= repetitions <= 1000:
        raise ValueError('repetitions must be an integer from 1 to 1000.')
    rng = np.random.default_rng(seed)
    scenarios = [('ideal', 0, 1, 1), ('noise_0_1pct', .001, 1, 1),
                 ('noise_1pct', .01, 1, 1), ('noise_5pct', .05, 1, 1),
                 ('line_impedance_plus_20pct', 0, 1.2, 1), ('remote_ct_plus_10pct', 0, 1, 1.1)]
    grid = list(product((.05, .25, .5, .75, .95), (.1, 1, 10, 1000), (-1.13, 0, math.pi)))
    rows = []
    for name, noise, z_scale, ct_scale in scenarios:
        for m, ratio, angle in grid:
            state = sequence_case(m, ratio, angle)
            vs, is_, vr, ir = state['quantities']
            floors = [max(abs(vs), abs(vr)), max(abs(is_), abs(ir))]*2
            for repetition in range(repetitions):
                windows = [np.full(24, v, complex) + noise*floor*(rng.normal(size=24)+1j*rng.normal(size=24))/math.sqrt(2)
                           for v, floor in zip((vs, is_, vr, ir), floors, strict=True)]
                windows[3] *= ct_scale
                estimate = e5_unsynchronised(*windows, z_scale*state['z1'])
                if estimate.ok and not math.isfinite(estimate.m):
                    raise ValueError('Solver marked a nonfinite distance as usable.')
                located = estimate.ok and 0 <= estimate.m <= 1
                interval = estimate.spread
                contains = bool(interval[0]-INTERVAL_ROUNDOFF_PU <= m <= interval[1]+INTERVAL_ROUNDOFF_PU) if located and interval else None
                rows.append({'case_id': f'{name}:{m}:{ratio}:{angle}:{repetition}', 'scenario': name,
                             'true_m': m, 'source_ratio': ratio, 'remote_rotation_radians': angle,
                             'noise_fraction': noise, 'line_impedance_scale': z_scale, 'remote_ct_scale': ct_scale,
                             'located': located, 'estimated_m': estimate.m if located else None,
                             'error_pct': 100*abs(estimate.m-m) if located else None,
                             'interval_contains_truth': contains,
                             'residual': estimate.residual if math.isfinite(estimate.residual) else None,
                             'reason': '' if located else ('outside protected line' if estimate.ok else estimate.reason)})
    return {'schema': 'dranalyser.numerical-envelope.v1', 'seed': seed, 'repetitions': repetitions,
            'window_samples': 24, 'interval_roundoff_pu': INTERVAL_ROUNDOFF_PU, 'summary': summarize(rows),
            'by_scenario': {name: summarize([r for r in rows if r['scenario'] == name]) for name, *_ in scenarios},
            'by_source_ratio': {str(ratio): summarize([r for r in rows if r['source_ratio'] == ratio])
                                for ratio in (.1, 1, 10, 1000)}, 'cases': rows,
            'limits': 'Synthetic passive negative-sequence branch experiment only. Noise is independently '
                      'specified complex Gaussian phasor noise, not a CT/CVT acquisition or phase-fault model. '
                      'Source ratio controls the remote negative-sequence source impedance. Errors are conditional '
                      'on in-line located cases; all planned cases remain in success/refusal fractions. '
                      'Interval containment allows 32 machine eps solely for floating-point roundoff; '
                      'it is descriptive, not calibrated confidence, field accuracy or TB 854 acceptance.'}
