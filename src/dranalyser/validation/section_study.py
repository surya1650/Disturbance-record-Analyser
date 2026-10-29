"""Validation-only aligned negative-sequence search on series-only sections.

This does not enable a production model. Both terminal phasors must already
share a reference. Sections are transposed/uncoupled, Z2=Z1, with no charging,
tap, internal source, series capacitor or distributed acquisition model.
"""
import math

import numpy as np


def aligned_section_candidates(line, vs, is_, vr, ir, *, tolerance=1e-8):
    """Return every eligible section projection, never choose among distinct fits.

    tolerance is a numerical relative voltage-mismatch bound for this study,
    not measurement uncertainty or a field-accuracy threshold. A 'unique'
    result means unique under these declared inputs and this numerical bound.
    """
    out = {'status': 'withheld', 'candidates': [], 'reason': '',
           'relative_voltage_tolerance': tolerance,
           'limits': 'Validation-only aligned, uncoupled series-section study; not an operational '
                     'location, unsynchronised estimator, calibrated interval or field acceptance.'}
    if not math.isfinite(tolerance) or not 0 <= tolerance <= .25:
        raise ValueError('Numerical study tolerance must be finite and between 0 and .25.')
    if line.model_review_required or line.double_circuit or line.series_compensated or not line.sections:
        out['reason'] = 'Unreviewed, coupled, compensated or missing section model.'
        return out
    previous, seen = 0.0, set()
    for section in line.sections:
        zero = [v for v in (section.r0, section.x0) if v is not None]
        values = (section.from_km, section.to_km, section.r1, section.x1, section.b1, section.b0, *zero)
        if (not all(math.isfinite(v) for v in values) or section.to_km <= section.from_km or
                not math.isclose(section.from_km, previous, rel_tol=0, abs_tol=1e-8) or
                section.x1 <= 0 or min([section.r1, *zero]) < 0 or
                section.b1 != 0 or section.b0 != 0 or section.seq in seen):
            out['reason'] = 'Invalid/noncontiguous sections, duplicate locators or unsupported shunt admittance.'
            return out
        previous = section.to_km
        seen.add(section.seq)
    if not all(np.isfinite(v) for v in (vs, is_, vr, ir)):
        out['reason'] = 'Nonfinite sequence measurements.'
        return out
    if abs(is_+ir) <= 1e-12*max(abs(is_), abs(ir), 1e-300):
        out['reason'] = 'Absent or cancelling fault-current sequence; section position is unidentifiable.'
        return out
    total, prefix = line.z1, 0j
    voltage_scale = max(abs(vs), abs(vr), abs(total*is_), abs(total*ir), 1e-12)
    for section in line.sections:
        z = section.z1
        suffix = total-prefix-z
        local_s, local_r = vs-prefix*is_, vr-suffix*ir
        fraction_complex = (local_s-local_r+z*ir)/(z*(is_+ir))
        prefix += z
        if not np.isfinite(fraction_complex) or not -1e-10 <= fraction_complex.real <= 1+1e-10:
            continue
        u = float(fraction_complex.real)
        u = 0.0 if abs(u) <= 1e-10 else 1.0 if abs(u-1) <= 1e-10 else u
        mismatch = abs((local_s-u*z*is_)-(local_r-(1-u)*z*ir))/voltage_scale
        if not math.isfinite(mismatch) or mismatch > tolerance:
            continue
        km = section.from_km+u*section.length_km
        # Merge only the same section junction, not arbitrary nearby roots.
        duplicate = next((c for c in out['candidates'] if u in (0, 1) and c['at_junction'] and
                          math.isclose(km, c['km_from_S'], rel_tol=0, abs_tol=1e-8)), None)
        if duplicate:
            duplicate['section_sequences'].append(section.seq)
            duplicate['relative_voltage_mismatch'] = max(duplicate['relative_voltage_mismatch'], float(mismatch))
        else:
            out['candidates'].append({'km_from_S': km, 'reactance_fraction_from_S': line.km_to_m(km),
                                      'section_sequences': [section.seq], 'section_fraction': u,
                                      'at_junction': u in (0, 1), 'relative_voltage_mismatch': float(mismatch)})
    count = len(out['candidates'])
    out.update(status='unique' if count == 1 else 'ambiguous' if count > 1 else 'withheld',
               reason='One section-compatible numerical fit.' if count == 1 else
                      'Distinct section fits retained; no automatic selection.' if count > 1 else
                      'No section-compatible fit within the declared numerical tolerance.')
    return out
