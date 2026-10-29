"""Guarded two-ended negative-sequence solving on uncoupled series sections.

Z2=Z1, both currents enter the line. No charging, taps or internal sources.
Screens below are engineering bounds, not calibrated uncertainty estimates.
"""
import math

import numpy as np

from .estimators import e5_delta, e5_roots


def section_model_reasons(line):
    """Validate the electrical domain independently of operational opt-in."""
    reasons = []
    if line.model_review_required:
        reasons.append('Electrical model/topology review remains required.')
    if line.double_circuit or line.series_compensated:
        reasons.append('Coupling or series compensation is unsupported by the section solver.')
    if not line.sections:
        return reasons + ['No line sections supplied.']
    previous, seen = 0.0, set()
    for s in line.sections:
        zero = [v for v in (s.r0, s.x0) if v is not None]
        values = (s.from_km, s.to_km, s.r1, s.x1, s.b1, s.b0, *zero)
        if (not all(math.isfinite(v) for v in values) or s.to_km <= s.from_km or
                not math.isclose(s.from_km, previous, rel_tol=0, abs_tol=1e-8) or
                s.x1 <= 0 or min([s.r1, *zero]) < 0 or s.seq in seen):
            return reasons + ['Invalid/noncontiguous sections or duplicate section identifiers.']
        if s.b1 != 0 or s.b0 != 0:
            reasons.append('Declared shunt admittance: charging is unsupported.')
        previous = s.to_km
        seen.add(s.seq)
    if not np.isfinite(line.z1) or not math.isfinite(line.length_km):
        reasons.append('Nonfinite total line impedance or length.')
    return list(dict.fromkeys(reasons))


def section_candidates(line, vs, is_, vr, ir, *, aligned=False):
    """Enumerate every in-line solution; never select among distinct locations."""
    out = {'status': 'withheld', 'candidates': [], 'reason': ''}
    reasons = section_model_reasons(line)
    if reasons:
        out['reason'] = ' '.join(reasons)
        return out
    if not all(np.isfinite(v) for v in (vs, is_, vr, ir)):
        out['reason'] = 'Nonfinite negative-sequence measurements.'
        return out
    scale = max(abs(vs), abs(vr), abs(is_), abs(ir))
    if scale == 0:
        out['reason'] = 'Absent negative-sequence measurements.'
        return out
    vs, is_, vr, ir = (v/scale for v in (vs, is_, vr, ir))
    total, prefix = line.z1, 0j
    vscale = max(abs(vs), abs(vr), abs(total*is_), abs(total*ir), 1e-300)
    if not math.isfinite(vscale):
        out['reason'] = 'Nonfinite propagated voltage scale.'
        return out
    unidentifiable = False
    for index, sec in enumerate(line.sections):
        z = sec.z1
        suffix = total-prefix-z
        left, right = vs-prefix*is_, vr-suffix*ir
        prefix += z
        if aligned:
            den = z*(is_+ir)
            if abs(den) <= 1e-12*max(abs(z*is_), abs(z*ir), 1e-300):
                unidentifiable = True
                continue
            mc = (left-right+z*ir)/den
            roots = [float(mc.real)] if np.isfinite(mc) else []
        else:
            roots, _, how = e5_roots(left, is_, right, ir, z)
            if how.startswith('degenerate'):
                unidentifiable = True
        for u in roots:
            if not -1e-10 <= u <= 1+1e-10:
                continue
            u = 0.0 if abs(u) <= 1e-10 else 1.0 if abs(u-1) <= 1e-10 else float(u)
            fs, fr = left-u*z*is_, right-(1-u)*z*ir
            mismatch = (abs(fs-fr) if aligned else abs(abs(fs)-abs(fr)))/vscale
            if not math.isfinite(mismatch) or mismatch > (0.01 if aligned else 1e-8):
                continue
            delta = 0.0 if aligned else e5_delta(u, left, is_, right, ir, z)
            km = sec.from_km+u*sec.length_km
            duplicate = next((c for c in out['candidates'] if u == 0 and c['at_junction'] and
                              c['section_indices'][-1] == index-1 and
                              math.isclose(km, c['km_from_S'], rel_tol=0, abs_tol=1e-8)), None)
            if duplicate:
                duplicate['section_sequences'].append(sec.seq)
                duplicate['section_indices'].append(index)
                if not math.isfinite(delta):
                    duplicate['delta_rad'] = None
                duplicate['relative_voltage_mismatch'] = max(duplicate['relative_voltage_mismatch'], float(mismatch))
            else:
                out['candidates'].append(dict(km_from_S=float(km), m=float(line.km_to_m(km)),
                    section_sequences=[sec.seq], section_indices=[index], section_fraction=u,
                    at_junction=u in (0, 1), delta_rad=float(delta) if math.isfinite(delta) else None,
                    relative_voltage_mismatch=float(mismatch)))
    out['candidates'].sort(key=lambda c: c['km_from_S'])
    count = len(out['candidates'])
    if unidentifiable:
        out.update(status='ambiguous', reason='At least one section constraint is unidentifiable.')
    elif count > 1:
        out.update(status='ambiguous', reason='Multiple distinct in-line section roots; no automatic selection.')
    elif count == 1:
        out.update(status='unique', reason='One in-line section candidate.')
    else:
        out['reason'] = 'No in-line section candidate satisfies the measurements.'
    return out


def section_window(line, vs, is_, vr, ir, *, aligned=False):
    """Require a unique candidate at every sample and stable distance/angle."""
    out = dict(status='withheld', m=None, km_from_S=None, interval_pu=None,
               reason='', diagnostics={'model': 'series-sections', 'aligned': bool(aligned)})
    lengths = [len(v) for v in (vs, is_, vr, ir)]
    if len(set(lengths)) != 1 or lengths[0] < 2:
        out['reason'] = 'Equal windows with at least two samples required.'
        return out
    if not np.all(np.isfinite([vs, is_, vr, ir])):
        out['reason'] = 'Nonfinite negative-sequence window.'
        return out
    candidates = []
    for sample, values in enumerate(zip(vs, is_, vr, ir, strict=True)):
        result = section_candidates(line, *values, aligned=aligned)
        if result['status'] != 'unique':
            out.update(reason=result['reason'])
            out['diagnostics'].update(invalid_sample=sample, candidate_result=result)
            return out
        candidate = result['candidates'][0]
        if candidate['delta_rad'] is None:
            out['reason'] = 'Recovered fault-voltage angle is undefined.'
            out['diagnostics']['invalid_sample'] = sample
            return out
        candidates.append(candidate)
    ms = np.array([c['m'] for c in candidates])
    angles = np.array([c['delta_rad'] for c in candidates])
    resultant = min(1.0, max(1e-300, float(abs(np.mean(np.exp(1j*angles))))))
    angle_std = math.degrees(math.sqrt(-2*math.log(resultant)))
    spread = float(np.ptp(ms))
    out['diagnostics'].update(n_samples=lengths[0], delta_std_deg=angle_std,
        distance_spread_pu=spread, section_sequences=sorted({s for c in candidates for s in c['section_sequences']}),
        relative_voltage_mismatch=max(c['relative_voltage_mismatch'] for c in candidates))
    if angle_std > 5 or spread > .02:
        out['reason'] = 'Recovered angle or distance is unstable across the paired window.'
        return out
    m = float(np.median(ms))
    out.update(status='located', m=m, km_from_S=float(line.m_to_km(m)),
               interval_pu=[float(np.min(ms)), float(np.max(ms))],
               reason='Unique section-compatible location across every paired sample.')
    return out
