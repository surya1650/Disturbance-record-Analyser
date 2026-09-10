"""Conservative prerequisites for ground-loop and settings-outline display."""
import math


def _declared(value):
    """Keep invalid native values visible without emitting non-standard JSON."""
    return str(value) if isinstance(value, float) and not math.isfinite(value) else value


def display_context(an, settings=None, binding=None, review=None):
    binding, review = binding or {}, review or {}
    common = []
    if settings is None or binding.get('status') != 'associated export':
        common.append('A uniquely associated supported settings export is required.')
    if not review:
        common.append('No per-record R-X input review supplied.')
    elif (review.get('record_hash') != an.record.content_hash
          or not binding.get('sha256') or review.get('settings_hash') != binding['sha256']
          or review.get('channel_mapping', {}) != an.record.notes.get('channel_mapping', {})):
        common.append('Review is stale: recording, settings or channel mapping differs.')
    for key, label in [('settings_identity', 'Settings belong to this relay'),
                       ('effective_at_event', 'Settings were effective at the fault time'),
                       ('phase_scaling_polarity', 'Phase identities, primary scaling and bus-to-line current polarity')]:
        if review.get(key) is not True:
            common.append(label+' has not been confirmed by the reviewer.')
    ground, zones = list(common), list(common)
    if review.get('zero_sequence_voltage') is not True:
        ground.append('Phase-to-earth VT channels passing zero sequence have not been confirmed.')
    k0 = None
    if settings is not None:
        if settings.impedance_correction:
            ground.append('Enabled impedance correction is unsupported in this display.')
            zones.append('Enabled impedance correction is unsupported in this display.')
        if (settings.k0_convention not in ('siemens_re_xe', 'abb_kn', 'sel_k0', 'impedances')
                or (settings.k0_convention == 'siemens_re_xe' and 'line_angle_deg' in settings.unknown)):
            ground.append('Complete native compensation parameters are required; defaults/direct complex k0 are refused.')
        else:
            try:
                value = settings.k0()
                if value is None or not math.isfinite(value.real) or not math.isfinite(value.imag):
                    raise ValueError('nonfinite or missing compensation')
                k0 = value
            except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                ground.append('Native compensation cannot be derived as a finite value.')
    scale = None
    ratios = [review.get('ct_ratio'), review.get('vt_ratio')]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in ratios):
        zones.append('Reviewed CT and VT ratios for the settings secondary-ohm base are required.')
    elif settings is not None:
        scale = settings.secondary_to_primary(*ratios)
        if not math.isfinite(scale) or scale <= 0:
            zones.append('Settings-to-primary impedance conversion is not finite and positive.')
    return {'ground_missing': ground, 'zone_missing': zones, 'settings_source': binding,
            'compensation_source': {'convention': settings.k0_convention,
                                    'native_parameters': {k: _declared(v) for k, v in settings.k0_params.items()},
                                    'line_angle_deg': _declared(settings.line_angle_deg)} if settings else {},
            'review': review, 'k0': [k0.real, k0.imag] if k0 is not None and not ground else None,
            'primary_ohm_per_secondary_ohm': scale if not zones else None,
            'note': 'Reviewer declarations are not independently verified field inputs. Display only; exported boundaries '
                    'do not prove zone enablement, pickup, timing, relay algorithm or TB 854 validation.'}


def zone_outlines(settings, context):
    """Use exactly the requested characteristic kind, never Zone's fallback."""
    out = {'phase': [], 'earth': [], 'omitted': []}
    scale = context['primary_ohm_per_secondary_ohm']
    if settings is None or scale is None:
        return out
    for zone in settings.zones[:32]:
        for kind in ('phase', 'earth'):
            char = getattr(zone, kind)
            if char is None:
                out['omitted'].append(zone.name+' '+kind+': not supplied; no other kind substituted.')
                continue
            try:
                points = [[float(r)*scale, float(x)*scale] for r, x in char.outline()]
                if not 3 <= len(points) <= 512 or not all(math.isfinite(v) for p in points for v in p):
                    raise ValueError('invalid outline')
                area = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(points, points[1:]+points[:1], strict=True))
                if not math.isfinite(area) or abs(area) < 1e-12:
                    raise ValueError('degenerate outline')
                out[kind].append({'name': zone.name, 'points': points, 'unit': 'primary ohm'})
            except (ValueError, TypeError, NotImplementedError, OverflowError):
                out['omitted'].append(zone.name+' '+kind+': unsupported or invalid outline.')
    if len(settings.zones) > 32:
        out['omitted'].append('More than 32 zones; remaining outlines omitted.')
    return out
