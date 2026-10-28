"""Printable, source-bound combined inspection report; no operational verdict."""
from datetime import timedelta
import math

from jinja2 import Environment
from markupsafe import Markup

from .source_display import _recorded
from .source_inspection import _source, _rms, inspection_record


def _plot(points, boundaries, positive=False, extent=None):
    valid = [abs(p[2]) for p in points if p[2] is not None and math.isfinite(p[2])]
    scale = max(valid, default=1) or 1
    end = (extent if extent is not None else max((p[0] for p in points), default=1)) or 1
    paths, current, previous, boundary = [], [], None, 0
    for i, _, value in points:
        while previous is not None and boundary < len(boundaries) and boundaries[boundary] <= previous:
            boundary += 1
        crossed = previous is not None and boundary < len(boundaries) and boundaries[boundary] <= i
        if value is None or crossed:
            if current:
                paths.append(' '.join(current))
            current = []
        if value is not None:
            current.append(f'{60+i/end*730:.3f},{(95-value/scale*85 if positive else 50-value/scale*43):.3f}')
        previous = i
    if current:
        paths.append(' '.join(current))
    ticks = [0, scale/2, scale] if positive else [-scale, 0, scale]
    axes = ''.join(f'<line x1="60" x2="790" y1="{95-v/scale*85 if positive else 50-v/scale*43:.3f}" y2="{95-v/scale*85 if positive else 50-v/scale*43:.3f}" stroke="#dce5ea"/><text x="55" y="{98-v/scale*85 if positive else 53-v/scale*43:.3f}" text-anchor="end" font-size="10">{v:.4g}</text>' for v in ticks)
    return Markup(axes+''.join('<polyline points="'+p+'" fill="none" stroke="#176d82" stroke-width="1.2"/>' for p in paths))


def combined_report(root, row, filename, cursor=0):
    record = inspection_record(root, row, filename)
    source, _ = _source(root, row, filename)
    if not source.get('join'):
        raise ValueError('Select a combined timeline for this report.')
    if type(cursor) is not int or not 0 <= cursor < source['sample_count']:
        raise ValueError('Choose a cursor inside the combined recording.')
    meta = {c['id']: c for c in record['channels']}
    analog = []
    for c in source['channels']:
        values = [v for v in c['values'] if v is not None]
        rms = _rms(source, c)
        known = [v for v in rms['values'] if v is not None]
        analog.append(dict(id=c['key'], label=c['label'], units=c['units'],
            instant=c['values'][cursor], rms=rms['values'][cursor],
            minimum=min(values) if values else None, maximum=max(values) if values else None,
            rms_minimum=min(known) if known else None, rms_maximum=max(known) if known else None,
            waveform=_plot(meta[c['key']]['trace'], record['break_indices'], extent=source['sample_count']-1),
            trend=_plot(meta[c['key']]['rms_trace'], record['break_indices'], True, source['sample_count']-1)))
    times = source['axis']['elapsed_s']
    timeline = record['timeline']
    start = _recorded(source['recorded_times']['start'])
    relative = times[cursor]-(timeline['trigger_offset_s'] or 0)
    context = dict(name=row['name'], revision=row['number'], samples=source['sample_count'],
        cursor=cursor, origin=source['_origins'][cursor], relative_ms=relative*1000,
        reference_label="first capture's recorded trigger" if timeline['trigger_offset_s'] is not None else 'first sample (trigger unavailable)',
        local_time=(start+timedelta(seconds=times[cursor])).isoformat(timespec='microseconds'),
        analog=analog, digital=[meta[c['key']] for c in source['digital']],
        join=source['join'], hashes=source['source_sha256'], issues=record['issues'])
    env = Environment(autoescape=True)
    env.filters['number'] = lambda v: format(v, '.6g') if v is not None else 'Not available'
    template = '''<!doctype html><html><head><meta charset="utf-8"><title>Combined inspection report</title>
<style>body{font:14px system-ui,sans-serif;color:#233d4c;max-width:1100px;margin:30px auto;padding:0 20px}h1,h2{color:#153d4b}small{display:block;color:#607580}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #d6e1e7;padding:8px;vertical-align:top}section{margin:24px 0}svg{width:100%;height:110px;background:#f5f9fb}article{break-inside:avoid;margin:18px 0}.notice{padding:14px;background:#fff7e8;border-left:4px solid #c58d2e}.hash{overflow-wrap:anywhere;font:11px monospace}@media print{button{display:none}body{margin:0}}</style></head><body>
<button onclick="window.print()">Print / save PDF</button><h1>Combined inspection report</h1><p>{{ name }} · revision {{ revision }} · {{ samples }} retained samples</p>
<div class="notice">Derived same-relay source inspection. This report contains recorded observations and sample RMS, not a validated fault location, protection verdict or clock synchronization claim. Every original capture remains separate evidence.</div>
<section><h2>Capture timeline</h2><p>{{ join.clock_basis }}</p><p>{{ join.sample_policy }}</p><table><tr><th>Original capture</th><th>Start / end from joined start</th><th>Recorded trigger</th><th>Boundary</th></tr>{% for s in join.sources %}<tr><td>{{ s.file }}<small>{{ s.samples }} samples</small></td><td>{{ (s.start_s*1000)|number }} / {{ (s.end_s*1000)|number }} ms</td><td>{{ (s.trigger_s*1000)|number if s.trigger_s is not none else 'Unavailable' }} ms from joined start</td><td>{% if s.boundary_delta_s is none %}First capture{% elif s.boundary_delta_s < 0 %}{{ (-s.boundary_delta_s*1000)|number }} ms recorded overlap{% else %}{{ (s.boundary_delta_s*1000)|number }} ms between boundary samples{% endif %}</td></tr>{% endfor %}</table></section>
<section><h2>Cursor snapshot</h2><p>Joined sample {{ cursor }} · {{ relative_ms|number }} ms relative to {{ reference_label }} · {{ local_time }} relay-local time.</p><p>Original observation: {{ origin[0] }}, sample {{ origin[1] }} (zero based).</p><table><tr><th>Channel / source units</th><th>Instantaneous</th><th>Sample RMS · trailing nominal cycle</th><th>Observed range</th></tr>{% for c in analog %}<tr><td>{{ c.id }} {{ c.label }}<small>{{ c.units }}</small></td><td>{{ c.instant|number }}</td><td>{{ c.rms|number }}</td><td>{{ c.minimum|number }} to {{ c.maximum|number }}</td></tr>{% endfor %}</table><p>Sample RMS includes DC/harmonics and uses equal sample weights. Incomplete, missing, gapped and cross-capture supports remain unavailable. It is not the fitted fundamental phasor magnitude.</p></section>
<section><h2>Analog evidence</h2><p>Display envelopes on the common joined sample-index axis; gaps stay blank. Vertical scales are independent per channel. Exact cursor values are in the table above.</p>{% for c in analog %}<article><h3>{{ c.id }} {{ c.label }} · {{ c.units }}</h3><small>Waveform range {{ c.minimum|number }} to {{ c.maximum|number }}</small><svg viewBox="0 0 800 100" preserveAspectRatio="none">{{ c.waveform }}</svg><small>Sample RMS range {{ c.rms_minimum|number }} to {{ c.rms_maximum|number }}; zero-based vertical scale</small><svg viewBox="0 0 800 100" preserveAspectRatio="none">{{ c.trend }}</svg></article>{% endfor %}</section>
<section><h2>Digital observations</h2><p>Recorded state 1 is not automatically an asserted trip. Source boundaries leave onset/ending unknown; sample spans are not physical relay operating times.</p><table><tr><th>Channel</th><th>Observed changes</th><th>High-state sample spans from joined start</th></tr>{% for c in digital %}<tr><td>{{ c.id }} {{ c.label }}</td><td>{{ c.activity.transition_count }}</td><td>{% for v in c.activity.high_intervals %}<div>{{ (v.start_s*1000)|number if v.start_s is not none else 'Unknown' }} → {{ (v.last_s*1000)|number if v.last_s is not none else 'Unknown' }} ms{% if v.start_open %} · onset unknown{% endif %}{% if v.end_open %} · ending unknown{% endif %}</div>{% else %}No retained high-state interval{% endfor %}{% if c.activity.omitted_intervals %}<small>{{ c.activity.omitted_intervals }} further spans omitted by display budget</small>{% endif %}</td></tr>{% endfor %}</table></section>
<section><h2>Calculation limits and source provenance</h2><p>Cross-capture fundamental vectors and operational calculations are not enabled in this joined view. Inspect original captures for supported fundamental models. Re-uploading a combined COMTRADE export does not automatically clear timing/scaling or line-data requirements.</p><ul>{% for issue in issues %}<li>{{ issue }}</li>{% endfor %}</ul>{% for name, digest in hashes.items() %}<p class="hash">{{ name }} · SHA-256 {{ digest }}</p>{% endfor %}</section></body></html>'''
    return env.from_string(template).render(context)
