"""Refuse declared topology outside the scalar series-impedance model."""
import math

import numpy as np


def scalar_model_reasons(line):
    reasons = []
    if line.series_compensated:
        reasons.append('The line is series compensated: capacitor behavior is unsupported.')
    if line.double_circuit:
        reasons.append('Double-circuit line: coupled-network location is unvalidated; scalar distance withheld.')
    if not line.sections:
        return reasons + ['No line sections supplied.']
    ratios, previous = [], 0.0
    for s in line.sections:
        values = (s.from_km, s.to_km, s.r1, s.x1, s.r0, s.x0, s.b1, s.b0)
        if (not all(math.isfinite(v) for v in values) or s.to_km <= s.from_km or s.x1 <= 0 or
                s.r1 < 0 or s.r0 < 0 or s.x0 < 0 or not math.isclose(s.from_km, previous, abs_tol=1e-8)):
            reasons.append('Invalid/noncontiguous line sections; physical chainage and positive reactance required.')
            break
        previous = s.to_km
        if s.b1 != 0 or s.b0 != 0:
            reasons.append('Declared shunt admittance: the series-only scalar model omits charging; distance withheld.')
        ratios.append([s.r1/s.x1, s.r0/s.x1, s.x0/s.x1])
    if ratios and not np.allclose(ratios, ratios[0], rtol=1e-8, atol=1e-10):
        reasons.append('Nonproportional section impedances require section-aware electrical solving; '
                       'reactance-to-km conversion alone is insufficient.')
    return list(dict.fromkeys(reasons))
