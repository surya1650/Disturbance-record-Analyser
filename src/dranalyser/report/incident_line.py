"""Presentation of the frozen two-terminal circuit; no electrical inference."""
from __future__ import annotations

import math

from markupsafe import Markup, escape


def _text(value, limit=120):
    text = str(value or '').strip()
    return text if len(text) <= limit else text[:limit-1].rstrip()+'…'


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _km(value):
    if not _finite(value):
        return 'unavailable'
    if value == 0:
        return '0'
    return (f'{value:,.3f}'.rstrip('0').rstrip('.') if .001 <= abs(value) < 1000000
            else f'{value:.3g}')


def _observation(end, event, *, feedback=False):
    label = _text(event.get('signal'), 60) if feedback else 'Trip signal'
    label = label or 'Breaker feedback signal'
    kind = event.get('kind')
    bounds = event.get('source_bracket_s') or []
    if kind == 'state difference across gap' or event.get('transition_time_known') is False:
        local = ('–'.join(_km(t) for t in bounds)+' s local; transition time unknown') if len(bounds) == 2 else 'local transition time unknown'
        return end+': '+label+' differs across gap ('+local+')'
    reviewed = event.get('polarity_reviewed') is True and event.get('interpretation_available') is True
    state = (kind if kind in ('asserted', 'cleared') else 'changed') if reviewed else (
        'high state' if kind == 'asserted' else 'low state' if kind == 'cleared' else 'state changed')
    local = _km(event['source_s'])+' s local' if _finite(event.get('source_s')) else 'local time unavailable'
    return end+': '+label+' '+state+' at '+local+('' if reviewed else '; polarity unverified')


def _svg(diagram, terminals):
    line, fault = diagram.get('line') or {}, diagram.get('fault') or {}
    length = line.get('length_km')
    known_length = _finite(length) and length > 0
    distance, remote, fraction = (fault.get(k) for k in ('km_from_S', 'km_from_R', 'position_fraction'))
    show_fault = (fault.get('status') == 'eligible' and bool(fault.get('method')) and known_length
        and all(_finite(v) for v in (distance, remote, fraction))
        and 0 <= distance <= length and 0 <= remote <= length and 0 <= fraction <= 1
        and math.isclose(distance+remote, length, rel_tol=1e-9, abs_tol=1e-8)
        and math.isclose(fraction, distance/length, rel_tol=1e-9, abs_tol=1e-10))
    title = ('Circuit between '+terminals['S']['label']+' and '+terminals['R']['label'])
    description = ('Circuit breaker positions are unknown. Full line length: '
        +(_km(length)+' km. ' if known_length else 'unavailable. ')
        + ('Calculated fault '+_km(distance)+' km from S and '+_km(remote)+' km from R, by '+str(fault['method'])+'.'
           if show_fault else 'No eligible fault marker is shown.'))
    out = ['<svg class="line-diagram" viewBox="0 0 680 158" role="img" '
           'aria-labelledby="incident-line-title incident-line-description">',
        '<title id="incident-line-title">'+str(escape(title))+'</title>',
        '<desc id="incident-line-description">'+str(escape(description))+'</desc>',
        '<text x="340" y="19" text-anchor="middle" class="diagram-total">Full line length: '
            +str(escape(_km(length)+' km' if known_length else 'unavailable'))+'</text>']
    for end, bus, cb in (('S', 50, 123), ('R', 630, 557)):
        out.extend([
            f'<text x="{bus}" y="45" text-anchor="middle">{end}</text>',
            f'<line x1="{bus}" x2="{bus}" y1="57" y2="100" class="diagram-bus"/>',
            f'<line x1="{min(bus, cb)}" x2="{max(bus, cb)}" y1="78" y2="78" class="diagram-wire"/>',
            f'<rect x="{cb-13}" y="65" width="26" height="26" rx="1" class="diagram-cb" '
                f'aria-label="Circuit breaker at {end}: position unknown"/>',
            f'<text x="{cb}" y="84" text-anchor="middle" class="diagram-question">?</text>',
            f'<text x="{cb}" y="117" text-anchor="middle">CB {end}</text>'])
    out.append('<line x1="136" x2="544" y1="78" y2="78" class="diagram-circuit" '
        +('stroke-dasharray="6 4" ' if diagram.get('status') == 'generic schematic' else '')
        +'data-line-start="136" data-line-end="544"/>')
    if show_fault:
        position = 136+408*fraction
        out.extend([
            f'<g class="fault-marker" data-position-fraction="{fraction:.15g}" '
                f'data-km-from-s="{distance:.15g}" data-km-from-r="{remote:.15g}">',
            f'<path d="M {position-6:.4f} 69 L {position+6:.4f} 87 M {position+6:.4f} 69 L {position-6:.4f} 87"/>',
            f'<text x="{position:.4f}" y="55" text-anchor="middle">Fault</text></g>',
            '<text x="24" y="148">'+str(escape(_km(distance)+' km from S'))+'</text>',
            '<text x="656" y="148" text-anchor="end">'+str(escape(_km(remote)+' km from R'))+'</text>'])
    else:
        out.append('<text x="340" y="148" text-anchor="middle">Fault position unavailable</text>')
    out.append('</svg>')
    return Markup(''.join(out)), show_fault


def line_diagram_view(value):
    """Return bounded labels and safe SVG; old models keep their saved layout."""
    if not isinstance(value, dict) or value.get('version') != 1:
        return None
    line, fault = value.get('line') or {}, value.get('fault') or {}
    supplied = value.get('terminals') or {}
    terminals = {end: dict(label=_text((supplied.get(end) or {}).get('label') or 'End '+end, 110))
                 for end in ('S', 'R')}
    observations = []
    for end in ('S', 'R'):
        breaker = (supplied.get(end) or {}).get('breaker') or {}
        feedback = breaker.get('feedback_observations') or []
        trips = breaker.get('trip_observations') or []
        # One bounded observation per terminal: feedback, when recorded, is
        # more useful here than duplicating a command. Neither sets CB state.
        if feedback or trips:
            observations.append(_observation(end, (feedback or trips)[0], feedback=bool(feedback)))
    svg, has_fault = _svg(value, terminals)
    length = line.get('length_km')
    identity = ' · '.join(_text(line.get(k), 80) for k in ('id', 'name')
                        if line.get(k) and str(line[k]) != 'Not available')
    if _finite(line.get('kv')) and line['kv'] > 0:
        identity += (' · ' if identity else '')+_km(line['kv'])+' kV'
    provenance = ('Declared line model ('+_text(line.get('parameter_status') or 'unverified', 35)+').'
        if line.get('sha256') else 'Generic schematic; line model not supplied.')
    reference = line.get('line_reference')
    if isinstance(reference, dict) and reference:
        source = reference.get('source') if isinstance(reference.get('source'), dict) else {}
        review = 'applicability reviewed by user' if reference.get('applicability_reviewed') is True else 'applicability unreviewed'
        citation = _text(source.get('locator') or source.get('title') or 'Published source', 120)
        if not source.get('locator') and source.get('printed_page'):
            citation += ', printed p. '+_text(source['printed_page'], 12)
        provenance += ' Published reference impedance (positive sequence); '+review+'; not measured for this line. Source: '+citation+'.'
    return dict(svg=svg, identity=identity or 'Circuit identity not supplied', terminals=terminals,
        has_fault=has_fault, method=_text(fault.get('method'), 60) if has_fault else '',
        length=_km(length), reason=_text(fault.get('reason'), 400) if not has_fault else '',
        observations=observations,
        provenance_note=provenance,
        state_note='CB (circuit breaker) can disconnect the line; open/closed state unknown. Bay layout unverified.',
        connections_note=_text((value.get('connections') or {}).get('note') or
            'Only this two-terminal circuit is shown; other connected lines are not supplied.', 220))
