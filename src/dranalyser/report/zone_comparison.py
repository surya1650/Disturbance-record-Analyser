"""Conditional exported-boundary containment, not a protection-operation verdict.

IEEE C37.114-2014 fault loops are reused from loop_quantities. Primary V/I
impedance is divided once by the reviewed VT/CT settings-base conversion, then
the native Characteristic.contains decides membership. No estimator, window,
source, settings, polarity or compensation is changed by this adapter.
"""
import math
import re

import numpy as np

from ..dsp.window_quality import NAMES, window_transition
from ..faultloc.estimators import GROUND_LOOP, PHASE_LOOP, loop_quantities
from ..registry.settings import MhoChar, PolygonChar
from ..rules.signals import CANONICAL
from ..signals import ANALOG_CANON
from .rx_context import display_context, finite_number

CURRENT_FLOOR_A = 1e-6  # Existing R-X display numerical policy, not relay pickup.
MAX_SUPPORTS = 4096
MAX_ZONES = 32
_CONFIRMATIONS = ('settings_identity', 'effective_at_event', 'phase_scaling_polarity', 'zero_sequence_voltage')
_INPUT_ERRORS = (ValueError, TypeError, AttributeError, KeyError, OverflowError, ZeroDivisionError)


def _hash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _mapping(value):
    """Validate the public mapping boundary without importing the workbench."""
    if value is None or value == {}:
        return {}
    if not isinstance(value, dict) or set(value) - {'record_hash', 'reason', 'analog', 'digital'}:
        raise ValueError('Malformed reviewed channel mapping.')
    if (not _hash(value.get('record_hash')) or not isinstance(value.get('reason'), str)
            or not value['reason'].strip() or len(value['reason']) > 1000):
        raise ValueError('Reviewed channel mapping needs its recording hash and evidence.')
    out = dict(record_hash=value['record_hash'], reason=value['reason'].strip())
    for kind, prefix, targets in (('analog', 'A', ANALOG_CANON), ('digital', 'D', CANONICAL)):
        choices = value.get(kind, {})
        if not isinstance(choices, dict) or len(choices) > 2000:
            raise ValueError('Malformed reviewed channel mapping choices.')
        if any(not isinstance(k, str) or not re.fullmatch(prefix+'[1-9][0-9]*', k)
               or v not in (*targets, 'ignore') for k, v in choices.items()):
            raise ValueError('Unsupported reviewed channel identity or meaning.')
        out[kind] = dict(choices)
    return out if out['analog'] or out['digital'] else {}


def _review(value):
    """Match intake's declared review contract; maths remains in shared modules."""
    fields = {'record_hash', 'settings_hash', 'channel_mapping', 'reviewer', 'reason', 'ct_ratio', 'vt_ratio', *_CONFIRMATIONS}
    if not isinstance(value, dict) or not value or set(value) - fields:
        raise ValueError('A current per-record R-X input review is required; malformed/extra fields are refused.')
    out = {}
    for key in ('record_hash', 'settings_hash'):
        if not _hash(value.get(key)):
            raise ValueError('R-X input review needs exact recording and settings hashes.')
        out[key] = value[key]
    for key, limit in (('reviewer', 200), ('reason', 1000)):
        if not isinstance(value.get(key), str) or not value[key].strip() or len(value[key]) > limit:
            raise ValueError('R-X input review needs reviewer and supporting evidence within its length limits.')
        out[key] = value[key].strip()
    out['channel_mapping'] = _mapping(value.get('channel_mapping'))
    for key in _CONFIRMATIONS:
        if type(value.get(key, False)) is not bool:
            raise ValueError('R-X review confirmations must be explicit booleans.')
        out[key] = value.get(key, False)
    for key in ('ct_ratio', 'vt_ratio'):
        v = value.get(key)
        if v is not None and (not finite_number(v) or v <= 0):
            raise ValueError('Reviewed settings CT/VT ratios must be finite and positive, or absent.')
        out[key] = v
    return out


def _cross(a, b, c):
    value = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    if not math.isfinite(value):
        raise ValueError('Polygon arithmetic is nonfinite.')
    return value


def _intersects(a, b, c, d):
    p, q, r, s = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    def between(x, y, z):
        return min(x[0], y[0]) <= z[0] <= max(x[0], y[0]) and min(x[1], y[1]) <= z[1] <= max(x[1], y[1])
    return ((p > 0 > q or q > 0 > p) and (r > 0 > s or s > 0 > r)
            or p == 0 and between(a, b, c) or q == 0 and between(a, b, d)
            or r == 0 and between(c, d, a) or s == 0 and between(c, d, b))


def _geometry(characteristic):
    """Validate bounded native geometry before contains can label it 'outside'."""
    if not isinstance(characteristic, (PolygonChar, MhoChar)):
        raise ValueError('Unsupported characteristic type; native containment is not qualified.')
    if isinstance(characteristic, MhoChar):
        d = characteristic.diameter
        if not np.isfinite(d) or not math.isfinite(abs(d)) or abs(d) <= 0:
            raise ValueError('Mho diameter must be finite and nonzero.')
    raw = characteristic.outline()
    if not 3 <= len(raw) <= 512:
        raise ValueError('Characteristic outline needs 3 to 512 finite vertices.')
    if any(not isinstance(p, (tuple, list)) or len(p) != 2 or not all(finite_number(v) for v in p) for p in raw):
        raise ValueError('Characteristic outline contains invalid or nonfinite vertices.')
    points = [(float(r), float(x)) for r, x in raw]
    if points[-1] == points[0]:
        points.pop()
    if len(points) < 3 or len(set(points)) != len(points):
        raise ValueError('Characteristic outline contains repeated/insufficient vertices.')
    area = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(points, points[1:]+points[:1], strict=True))
    if not math.isfinite(area) or abs(area) < 1e-12:  # Same numerical geometry policy as zone_outlines.
        raise ValueError('Characteristic outline is nonfinite or degenerate.')
    if isinstance(characteristic, PolygonChar):
        edges = list(zip(points, points[1:]+points[:1], strict=True))
        for i, (a, b) in enumerate(edges):
            for j in range(i+1, len(edges)):
                if j == i+1 or i == 0 and j == len(edges)-1:
                    continue
                if _intersects(a, b, *edges[j]):
                    raise ValueError('Self-intersecting characteristic polygon is unsupported.')


def _supports(an, out):
    """Exact full-cycle operational supports; no display thinning or new windows."""
    rec, ps, win = an.record, an.ps, an.window
    out['window'].update(t_start_s=win.t_start if finite_number(win.t_start) else None,
                         t_end_s=win.t_end if finite_number(win.t_end) else None,
                         mode=win.mode if isinstance(win.mode, str) else None,
                         cycles=win.cycles if finite_number(win.cycles) else None,
                         phasor_window_samples=int(ps.n_window) if isinstance(ps.n_window, (int, np.integer)) else None,
                         half_cycle=bool(ps.half_cycle))
    if rec.blocked() or an.saturation.detected or an.clipping:
        raise ValueError('Blocked acquisition, detected saturation or clipping withholds the boundary comparison.')
    if (not finite_number(rec.fs) or rec.fs <= 0 or not finite_number(an.freq) or an.freq <= 0
            or ps.fs != rec.fs or ps.freq != an.freq or rec.nrates != 1 or rec.n < 2
            or len(ps.t) != rec.n or not np.array_equal(ps.t, rec.t)
            or not np.all(np.isfinite(rec.t)) or np.any(np.diff(rec.t) <= 0)
            or not np.allclose(np.diff(rec.t), 1/rec.fs, rtol=.01, atol=1e-7)):
        raise ValueError('A finite increasing uniform single-rate source and matching phasor grid are required; gaps are refused.')
    if (ps.half_cycle or ps.n_window != int(round(rec.fs/an.freq)) or ps.n_window < 2
            or win.mode != 'full' or not all(finite_number(v) for v in (win.t_start, win.t_end, win.cycles))
            or win.t_end <= win.t_start or win.cycles < 1):
        raise ValueError('A supported full-cycle operational window is required; short/half-cycle support is not qualified.')
    if win.t_start < rec.t[0] or win.t_end > rec.t[-1]:
        raise ValueError('The requested operational window extends outside the source recording; partial support is refused.')
    if any(n not in ps.phasors or len(ps.phasors[n]) != rec.n or n not in rec.analog
           or n not in rec.analog_meta or not rec.analog_meta[n].normalised for n in NAMES):
        raise ValueError('Six mapped phase phasors with declared primary scaling are required.')
    ids = an.indices()
    out['window']['support_count'] = int(len(ids))
    ids = ids[ids >= max(ps.valid_from, ps.n_window)]
    if not len(ids):
        raise ValueError('No complete operational phasor supports remain after the initialized prefix is excluded.')
    if len(ids) > MAX_SUPPORTS:
        raise ValueError('Operational window exceeds 4096 phasor supports; comparison is unavailable, never thinned.')
    if np.any(ids < 0) or np.any(ids >= rec.n):
        raise ValueError('Operational phasor support is outside the source recording.')
    start, stop = int(ids[0]-ps.n_window+1), int(ids[-1]+1)
    if any(not np.all(np.isfinite(ps.phasors[n][ids])) or not np.all(np.isfinite(rec.analog[n][start:stop])) for n in NAMES):
        raise ValueError('Nonfinite phase values occur inside supported operational phasor/raw windows.')
    transition = window_transition(an)
    if transition['status'] == 'transition detected':
        raise ValueError('Detected mixed-state transitions withhold a pooled comparison; review separate stages.')
    if transition['status'] == 'not assessed':
        out['notes'].append('Transition screening is inconclusive: '+transition['reason'])
    out['window'].update(first_index=int(ids[0]), last_index=int(ids[-1]), raw_support_start_index=start,
                         raw_support_end_index=stop)
    return ids


def compare_zones(an, settings=None, binding=None, review=None):
    """Return versioned conditional counts over exact reviewed model supports."""
    fault = an.fault_type if isinstance(an.fault_type, str) else 'NONE'
    loop = fault if fault in GROUND_LOOP else ''.join(PHASE_LOOP.get(fault, ())) or None
    kind = 'earth' if fault in GROUND_LOOP else 'phase' if loop else None
    source = an.record.content_hash if _hash(an.record.content_hash) else None
    settings_hash = getattr(getattr(settings, 'provenance', None), 'sha256', None)
    settings_hash = settings_hash if _hash(settings_hash) else None
    out = dict(version=1, title='Reviewed zone-boundary comparison', status='not_evaluable',
               fault_type=fault, loop=loop, characteristic_kind=kind, record_hash=source,
               settings_hash=settings_hash, channel_mapping={}, review={}, binding={}, zones=[], reasons=[],
               window=dict(t_start_s=None, t_end_s=None, mode=None, cycles=None, phasor_window_samples=None,
                           half_cycle=False, support_count=None, evaluated_count=0, first_index=None, last_index=None,
                           raw_support_start_index=None, raw_support_end_index=None, raw_support_indexing='[start, stop)',
                           time_basis='Source-local seconds; fixed operational window, independent of display cursors.'),
               notes=['Counts are overlapping phasor supports, not independent observations or confidence coverage.',
                      'Containment does not establish zone enablement, pickup, timing, scheme behavior or correct operation.',
                      'Reviewed declarations remain conditional; no source samples, scaling, polarity or settings are repaired.',
                      'Native characteristic boundary conventions are retained; no boundary tolerance or fastest-zone inference is added.'],
               authorizes_operation=False)
    try:
        current_mapping = _mapping(an.record.notes.get('channel_mapping'))
        checked_review = _review(review)
        out.update(channel_mapping=current_mapping, review=checked_review)
        if not isinstance(binding, dict) or binding.get('status') != 'associated export':
            raise ValueError('A uniquely associated actual settings export is required.')
        saved_binding = {k: binding[k] for k in ('status', 'file', 'sha256') if isinstance(binding.get(k), str)}
        out['binding'] = dict(record_hash=source, settings_hash=settings_hash, channel_mapping=current_mapping,
                              review=checked_review, settings_source=saved_binding)
        if not source or not settings_hash or binding.get('sha256') != settings_hash:
            raise ValueError('Exact recording and actual-settings hashes must match the associated source inputs.')
        if checked_review['record_hash'] != source or checked_review['settings_hash'] != settings_hash or checked_review['channel_mapping'] != current_mapping:
            raise ValueError('The R-X review is stale: recording, settings or channel mapping differs.')
        if loop is None:
            raise ValueError('No supported classified fault loop is available for this comparison.')
        context = display_context(an, settings, binding, checked_review)
        missing = context['zone_missing'] + (context['ground_missing'] if kind == 'earth' else [])
        if kind == 'earth' and an.zero_seq_voltage is not True:
            missing.append('Detected VT evidence contradicts supported zero-sequence voltage transfer.')
        if missing:
            raise ValueError(' '.join(dict.fromkeys(missing)))
        if len(settings.zones) > MAX_ZONES:
            raise ValueError('Settings contain more than 32 exported zones; comparison is unavailable, never truncated.')
        if not settings.zones:
            raise ValueError('No exported zone boundaries are supplied.')
        out['zones'] = [dict(name=str(zone.name), index=i, kind=kind, status='not_evaluable', inside_count=0,
                             outside_count=0, evaluated_count=0, reasons=[]) for i, zone in enumerate(settings.zones)]
        ids = _supports(an, out)
        vph = {p: an.ps.phasors['V'+p][ids] for p in 'ABC'}
        iph = {p: an.ps.phasors['I'+p][ids] for p in 'ABC'}
        k0 = complex(*context['k0']) if kind == 'earth' else 0j
        vl, il, _ = loop_quantities(vph, iph, sum(iph.values())/3, k0, fault)
        if not np.all(np.isfinite(il)) or np.any(np.abs(il) <= CURRENT_FLOOR_A):
            raise ValueError('A supported loop current exceeds the 1e-6 A numerical floor only on complete supports; zero/weak points withhold comparison.')
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            points = vl / il / context['primary_ohm_per_secondary_ohm']
        if not np.all(np.isfinite(points)):
            raise ValueError('Loop projection or reviewed settings-base conversion is nonfinite.')
        for zone, row in zip(settings.zones, out['zones'], strict=True):
            try:
                characteristic = getattr(zone, kind)
                if characteristic is None:
                    raise ValueError('The exact '+kind+' characteristic is not supplied; another kind is never substituted.')
                _geometry(characteristic)
                membership = [characteristic.contains(complex(z)) for z in points]
                if any(not isinstance(value, (bool, np.bool_)) for value in membership):
                    raise ValueError('Native containment did not return boolean membership.')
                inside = sum(bool(value) for value in membership)
                row.update(status='inside' if inside == len(points) else 'outside' if inside == 0 else 'mixed',
                           inside_count=inside, outside_count=len(points)-inside, evaluated_count=len(points))
            except (*_INPUT_ERRORS, NotImplementedError) as exc:
                row['reasons'] = [str(exc) or 'Unsupported native characteristic.']
        if any(row['evaluated_count'] for row in out['zones']):
            out['status'] = 'available'
            out['window']['evaluated_count'] = len(points)
        else:
            out['reasons'].append('No exported boundary is evaluable for the exact classified loop.')
    except _INPUT_ERRORS as exc:
        out['reasons'].append(str(exc) or 'Supported source/settings/review inputs are unavailable.')
        for row in out['zones']:
            row['reasons'] = list(out['reasons'])
    return out
