"""Static R-X presentation reuses the source navigator's reviewed display contract."""
import re

from ..faultloc.estimators import GROUND_LOOP, PHASE_LOOP
from . import graphics
from .navigation import phase_loops
from .rx_context import display_context, finite_number, zone_outlines


def rx_model(an, end, settings, evidence):
    """Recompute from current source/settings; serialized k0 and scale are not inputs."""
    source_hash = an.record.content_hash
    matches = [row for row in evidence if row.get('end') == end and row.get('role') == 'primary'
               and row.get('status') == 'analysed' and re.fullmatch('[0-9a-f]{64}', source_hash or '')
               and row.get('record_hash') == an.record.content_hash]
    saved = matches[0].get('rx_context') if len(matches) == 1 else None
    saved = saved if isinstance(saved, dict) else {}
    binding, review = saved.get('settings_source'), saved.get('review')
    binding = binding if isinstance(binding, dict) else {}
    review = review if isinstance(review, dict) else {}
    reasons = []
    if len(matches) != 1:
        reasons.append('A uniquely matched primary recording is required for reviewed R-X overlays.')
    actual_hash = settings.provenance.sha256 if settings is not None else ''
    if not (re.fullmatch('[0-9a-f]{64}', actual_hash or '') and binding.get('sha256') == actual_hash):
        reasons.append('The associated settings hash must match the settings used by this report.')
        binding = {}
    if review and any(not isinstance(review.get(key), str) or not review[key].strip()
                      for key in ('reviewer', 'reason')):
        reasons.append('R-X reviewer identity and supporting evidence are required.')
        review = {}
    context = display_context(an, settings, binding, review)
    if reasons:
        context['ground_missing'].extend(reasons)
        context['zone_missing'].extend(reasons)
        context['k0'] = context['primary_ohm_per_secondary_ohm'] = None
    rx = phase_loops(an, context=context)
    if not rx['loops']:
        context['ground_missing'].append(rx['reason'])
        context['zone_missing'].append(rx['reason'])
        context['k0'] = context['primary_ohm_per_secondary_ohm'] = None
    fault = an.fault_type
    loop = fault if fault in GROUND_LOOP else ''.join(PHASE_LOOP.get(fault, ()))
    if not loop:
        reasons.append('No supported fault loop is available for this classification.')
    ground = loop in GROUND_LOOP
    reasons.extend(context['ground_missing'] if ground else [])
    reasons.extend(context['zone_missing'])
    rows = rx['loops'].get(loop, [])
    lo = float(an.notes.get('inception_t', 0))
    hi = lo + 6/an.freq
    trajectory = [complex(r, x) if r is not None and x is not None else None
                  for t, r, x in rows if lo <= t < hi]
    outlines = zone_outlines(settings, context)
    zones = [{'name': zone['name'], 'vertices': zone['points']}
             for zone in outlines['earth' if ground else 'phase']] if loop else []
    reasons.extend(outlines['omitted'])
    if not any(point is not None for point in trajectory):
        reasons.append('No supported trajectory for the selected loop in the displayed six-cycle interval.')
    angle = settings.line_angle_deg if settings is not None and not context['zone_missing'] else None
    if angle is not None and (not finite_number(angle) or 'line_angle_deg' in settings.unknown):
        reasons.append('A finite supplied line angle is required for the line-direction guide.')
        angle = None
    return dict(context=context, loop=loop, trajectory=trajectory, zones=zones,
                line_angle_deg=angle, reasons=list(dict.fromkeys(reasons)))


def render_rx(an, end, settings, evidence):
    model = rx_model(an, end, settings, evidence)
    html = graphics.rx_diagram(model['zones'], model['trajectory'], model['line_angle_deg'], unit='primary ohm')
    reasons = ''.join('<li>'+graphics.esc(reason)+'</li>' for reason in model['reasons'])
    return ('<section data-rx-display-version="2"><p>Loop '+graphics.esc(model['loop'] or 'unavailable')+
            ' · primary ohm · six nominal cycles from detected inception.</p>'+html+
            ('<ul>'+reasons+'</ul>' if reasons else '')+'</section>')
