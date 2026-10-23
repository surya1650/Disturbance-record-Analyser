"""Incident adapter for explicitly enabled negative-sequence section models."""
import math

import numpy as np

from ..dsp.detect import overlap_window
from ..dsp.window_quality import NAMES, window_transition
from .estimators import Estimate
from .sections import section_model_reasons, section_window


def section_incident(line, terminals, fault, caveats, cross_country=False):
    """Return LocationResult fields, keeping all scalar fallback paths closed."""
    nan = float('nan')
    out = dict(m=nan, km_from_S=nan, km_from_R=nan, interval_pu=(nan, nan),
               interval_km=(nan, nan), method='none', mode='none', fault_type=fault,
               caveats=list(caveats)+[
                   'Opt-in uncoupled series-section model, Z2=Z1; no charging or internal sources.',
                   'Sample spread is descriptive, not calibrated confidence; no automatic tower assignment.'],
               diagnostics={'model_domain': 'series-sections'})

    def refuse(reason):
        out['caveats'].append(reason)
        return out

    reasons = section_model_reasons(line)
    if line.section_solver_enabled is not True:
        reasons.append('Section solver opt-in must be a boolean true.')
    if reasons:
        return refuse(' '.join(reasons))
    if set(terminals) != {'S', 'R'} or cross_country or fault in ('ABC', 'ABCG', 'NONE'):
        return refuse('Two same-fault terminal records with usable negative sequence are required; no scalar fallback.')
    s, r = terminals['S'], terminals['R']
    for ti in (s, r):
        an = ti.analysed
        if (ti.polarity not in (-1, 1) or an.record.blocked() or an.record.nrates > 1 or
                an.saturation.detected or an.clipping):
            return refuse('Blocked acquisition, invalid polarity, saturation or clipping; section incident withheld.')
        if (not math.isfinite(an.freq) or an.freq <= 0 or not math.isfinite(an.record.fs) or an.record.fs <= 0 or
                not np.allclose(np.diff(an.record.t), 1/an.record.fs, rtol=.01, atol=1e-7) or
                any(n not in an.ps.phasors for n in (*NAMES, 'V2', 'I2', 'I1'))):
            return refuse('Unsupported sampling grid or missing phase/sequence phasors.')
        if window_transition(an)['status'] == 'transition detected':
            return refuse('Nonstationary analysis window: use separately reviewed stages.')
    shift = float(s.analysed.notes.get('inception_t', 0))-float(r.analysed.notes.get('inception_t', 0))
    overlap = overlap_window(s.analysed.window, r.analysed.window, s.analysed.freq, shift_b=shift)
    if overlap.cycles < .5 or not math.isfinite(overlap.cycles):
        return refuse('Insufficient corresponding local-window support; no scalar fallback.')
    spans = [(overlap.t_start, overlap.t_end), (overlap.t_start-shift, overlap.t_end-shift)]
    indices = [ti.analysed.ps.window_indices(*span) for ti, span in zip((s, r), spans, strict=True)]
    count = min(24, *(len(i) for i in indices))
    if count < 2:
        return refuse('At least two complete paired phasor supports are required.')
    quantities = []
    for ti, ids in zip((s, r), indices, strict=True):
        an = ti.analysed
        values = np.array([an.ps.phasors[n][ids] for n in (*NAMES, 'V2', 'I2', 'I1')])
        if not np.all(np.isfinite(values)):
            return refuse('Nonfinite phase or sequence measurements within the selected support.')
        # Check the complete selected window before the bounded solver sampling.
        i2, i1 = an.ps.phasors['I2'][ids], an.ps.phasors['I1'][ids]
        if np.min(abs(i2)) < max(.01*float(np.median(abs(i1))), 1e-6):
            return refuse('Insufficient negative sequence at a terminal; section location withheld.')
        picks = ids[np.linspace(0, len(ids)-1, count).round().astype(int)]
        quantities.extend([an.ps.phasors['V2'][picks], an.ps.phasors['I2'][picks]*ti.polarity])
    aligned = s.clock_good is True and r.clock_good is True
    result = section_window(line, *quantities, aligned=aligned)
    out['diagnostics']['section_solver'] = result
    out['method'] = 'E4-sections' if aligned else 'E5-sections'
    if result['status'] != 'located':
        return refuse(result['reason'])
    m, km = result['m'], result['km_from_S']
    interval = tuple(result['interval_pu'])
    out.update(m=m, km_from_S=km, km_from_R=line.length_km-km, interval_pu=interval,
               interval_km=tuple(line.m_to_km(x) for x in interval), mode='two-ended',
               estimates=[Estimate(out['method'], m, result['diagnostics']['relative_voltage_mismatch'],
                                   ends='two', diagnostics=result['diagnostics'], spread=interval)])
    out['caveats'].append('Relative-position pairing is not timestamp synchronization or same-stage proof.')
    out['diagnostics']['_km_fn'] = line.m_to_km
    return out
