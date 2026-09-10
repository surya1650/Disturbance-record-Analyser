"""Source-reported clock quality, never an authorization to synchronize records.

Interpretation: IEEE PSRC WG H4, 2013 COMTRADE summary, slides 9-12,
https://www.pes-psrc.org/kb/report/1014.pdf. Numeric code bounds cross-checked
against GPA GSF.COMTRADE Schema.TimeQualityIndicatorCode (see validation doc).
No source accuracy, continuous lock history or event identity is inferred.
"""
from __future__ import annotations


def clock_quality(rec):
    raw = {k: rec.notes.get(k, '') for k in ('tmq_code', 'time_code', 'local_code', 'leapsec')}
    code = str(raw['tmq_code']).strip().upper()
    status, bound = 'unavailable', None
    if code == '0':
        status = 'source reports locked; accuracy unspecified'
    elif len(code) == 1 and code in '123456789AB':
        status = 'source reports unlocked with error bound'
        bound = 10.0 ** (int(code, 16)-10)
    elif code == 'F':
        status = 'source reports clock failure'
    elif code:
        status = 'unsupported clock-quality code'
    leap = str(raw['leapsec']).strip()
    leap_status = {'0': 'source reports no leap adjustment', '1': 'leap second added',
                   '2': 'leap second removed', '3': 'source lacks leap-second capability'}.get(
                       leap, 'leap-second handling unknown')
    reasons = ['Clock source accuracy and continuity over the capture are not independently established.',
               'UTC conversion and same-event/stage identity are not established; local timelines retained.']
    if bound is None:
        reasons.append('No numeric timestamp error bound is available from this code.')
    if leap != '0':
        reasons.append('Leap-second metadata does not establish an uninterrupted absolute timeline.')
    return {'version': 1, 'status': status, 'raw': raw, 'record_hash': rec.content_hash,
            'source': 'record CFG timing fields', 'reported_time_basis': rec.time_basis,
            'reported_error_bound_s': bound, 'uncertainty_s': None,
            'uncertainty_basis': 'reported bound is relative to the synchronizing source, not verified UTC accuracy',
            'leap_status': leap_status, 'verified': False, 'alignment_eligible': False,
            'applied': False, 'reasons': reasons,
            'reference': 'IEEE PSRC WG H4 2013 COMTRADE summary, slides 9-12'}
