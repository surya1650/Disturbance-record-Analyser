"""Bounded display data from an existing analysis; never an estimator input."""
from __future__ import annotations

import numpy as np

from ..faultloc.estimators import loop_quantities
from ..rules.evidence import point_observation
from ..rules.signals import map_signals
from .rx_context import display_context, zone_outlines

MAX_BINS = 1200
MAX_CHANNELS = 64
MAX_INTERVALS = 2000


def envelope(t, values, limit=MAX_BINS):
    """Keep extrema and time support of every bin, including missing-data gaps."""
    values = np.asarray(values)
    if len(values) != len(t):
        return []
    out = []
    for ids in np.array_split(np.arange(len(t)), min(limit, len(t))):
        if not len(ids):
            continue
        v = values[ids]
        valid = bool(np.all(np.isfinite(v)))
        out.append([float(t[ids[0]]), float(t[ids[-1]]),
                    float(np.min(v)) if valid else None, float(np.max(v)) if valid else None, len(ids)])
    return out


def phase_loops(an, limit=MAX_BINS, *, context=None):
    """Primary-ohm phase loops, using the existing loop definition and phasors."""
    rec, ps = an.record, an.ps
    needed = ['V'+p for p in 'ABC'] + ['I'+p for p in 'ABC']
    if any(k not in ps.phasors or k not in rec.analog_meta or not rec.analog_meta[k].normalised for k in needed):
        return {'reason': 'Mapped phase phasors and declared primary scaling are required.', 'loops': {}}
    if rec.nrates > 1 or np.any(np.diff(rec.t) > 1.5 / rec.fs):
        return {'reason': 'Multi-rate or gapped acquisition: R-X inspection is unavailable.', 'loops': {}}
    out = {}
    chunks = np.array_split(np.arange(len(ps.t)), min(limit, len(ps.t)))
    k0 = complex(*context['k0']) if context and context.get('k0') is not None else None
    for loop in ('AB', 'BC', 'CA') + (('AG', 'BG', 'CG') if k0 is not None else ()):
        values = np.full(len(ps.t), np.nan + 1j*np.nan)
        v = {p: ps.phasors['V'+p] for p in 'ABC'}
        current = {p: ps.phasors['I'+p] for p in 'ABC'}
        i0 = sum(current.values()) / 3
        vl, il, _ = loop_quantities(v, current, i0, k0 or 0j, loop)
        # Numerical display floor only; it is not relay pickup or accuracy validation.
        # The mimic filter's first sample is initialized, not measured history.
        # Keep its entire first DFT window out of this display.
        valid = (np.arange(len(ps.t)) >= max(ps.valid_from, ps.n_window)) & (np.abs(il) > 1e-6)
        np.divide(vl, il, out=values, where=valid)
        rows = []
        for ids in chunks:
            if not len(ids):
                continue
            i = int(ids[-1])
            good = bool(np.all(np.isfinite(values[ids])))
            rows.append([float(ps.t[i]), float(values[i].real) if good else None,
                         float(values[i].imag) if good else None])
        out[loop] = rows
    return {'reason': 'Primary ohm from declared scaling. Ground loops require the per-record input review. '
                      'Display points are thinned; gaps are retained. Current floor 1e-6 A is numerical policy.',
            'loops': out, 'dft_window_samples': ps.n_window,
            'point_policy': 'Last phasor of each bin only when every phasor in that bin is finite.'}


def navigation_record(an, evidence, settings=None, binding=None, review=None):
    rec = an.record
    if rec.n < 2 or not np.all(np.isfinite(rec.t)) or not np.all(np.diff(rec.t) > 0):
        return {'file': evidence['file'], 'status': 'unavailable', 'reason': 'A finite increasing sample timeline is required.'}
    mapped = map_signals(list(rec.digital), rec.notes.get('digital_overrides'))
    analog = []
    for name, values in list(rec.analog.items())[:MAX_CHANNELS]:
        meta = rec.analog_meta.get(name)
        analog.append({'name': name, 'source': meta.raw_id if meta else name,
                       'unit': ('A' if name.startswith('I') else 'V') if meta and meta.normalised else 'unknown',
                       'declared_unit': meta.unit if meta else 'unknown',
                       'scaling': 'declared primary' if meta and meta.normalised else 'unconfirmed',
                       'bins': envelope(rec.t, values)})
    digital = []
    continuous = rec.nrates <= 1 and not np.any(np.diff(rec.t) > 1.5 / rec.fs)
    for name in list(rec.digital)[:MAX_CHANNELS]:
        point = point_observation(rec, name, evidence['trigger_offset_s'])
        if not continuous or len(point['intervals']) > MAX_INTERVALS:
            point.update(state='unavailable for continuous navigation', intervals=[],
                         initially_active=False, assertions_ms=[], assertions_s=[])
        meanings = [s['signal'] for s in evidence['signals'] if name in mapped.channels(s['signal'])]
        digital.append(dict(point, meanings=meanings))
    context = display_context(an, settings, binding, review)
    rx = phase_loops(an, context=context)
    if not rx['loops']:
        context['ground_missing'].append(rx['reason'])
        context['zone_missing'].append(rx['reason'])
        context['k0'] = context['primary_ohm_per_secondary_ohm'] = None
    rx.update(context=context, zones=zone_outlines(settings, context))
    return {'file': evidence['file'], 'status': 'available',
            'capture_s': [float(rec.t[0]), float(rec.t[-1])], 'sample_count': rec.n,
            'analog': analog, 'digital': digital, 'rx': rx,
            'stages': evidence.get('stages'), 'clock_quality': evidence.get('clock_quality'),
            'omitted_analog': list(rec.analog)[MAX_CHANNELS:], 'omitted_digital': list(rec.digital)[MAX_CHANNELS:],
            'unmapped_analog': list(rec.notes.get('unmapped_channels') or []),
            'note': 'Display only. Each envelope bin retains min/max, support and sample count; it is not an exact cursor sample. '
                    'At most 64 mapped analog and 64 digital channels are displayed. Unmapped analogs remain in the source file. '
                    'Digital continuity is withheld for gaps/multi-rate data or more than 2000 active intervals. '
                    'Neither cursor selection nor display thinning changes analysis windows, times, rules or location.'}
