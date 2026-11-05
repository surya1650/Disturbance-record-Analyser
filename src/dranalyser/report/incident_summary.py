"""Four-page, offline incident report from a frozen reader-report model.

This module formats supplied evidence. It does not decode sources, select study
windows, calculate electrical quantities, or infer physical breaker operation.
"""
from __future__ import annotations

import math
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from .incident_line import line_diagram_view

_PHASES = {'IA': 'R (A)', 'IB': 'Y (B)', 'IC': 'B (C)',
           'VA': 'R (A)', 'VB': 'Y (B)', 'VC': 'B (C)'}
_COLORS = ('#cc3845', '#9b7300', '#2563b9')
_SIGNALS = {'START': 'Disturbance start indication', 'TRIP': 'Trip command indication',
            'CARRIER_SEND': 'Protection message sent', 'CARRIER_RECV': 'Protection message received',
            'CLOSE': 'Close command indication', 'Z1': 'Zone 1 indication', 'Z2': 'Zone 2 indication',
            'Z3': 'Zone 3 indication'}


def _text(value, limit=240):
    value = str(value or '').strip()
    return value if len(value) <= limit else value[:limit-1].rstrip()+'…'


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    if value == 0:
        return '0'
    magnitude = abs(value)
    return f'{value:.3g}' if magnitude < .01 or magnitude >= 100000 else f'{value:,.3f}'.rstrip('0').rstrip('.')


def _items(value, count, limit=240):
    return [_text(item, limit) for item in (value or [])[:count] if item]


def _unit(value):
    text = str(value or 'units not established').strip()
    # Preserve counts as counts; shorten only explicit known unit declarations.
    token = text.split(' ', 1)[0]
    return token if token in ('A', 'V', 'kA', 'kV', 'counts') else _text(text, 22)


def _display_scale(source, quantity):
    """Choose readable metric prefixes without establishing a physical scale."""
    base, prefix = ('A', 'I') if quantity == 'current' else ('V', 'V')
    entries = [(p.get('units'), [p.get(k) for k in ('pre_rms', 'fault_rms', 'post_rms')])
               for p in source.get('phase_values', []) if str(p.get('meaning', '')).startswith(prefix)]
    entries += [(c.get('units'), [p[2] for p in c.get('trace', [])[:4096]
                 if isinstance(p, (list, tuple)) and len(p) >= 3])
                for c in (source.get('groups') or {}).get(quantity, [])]
    entries += [(p.get('unit'), [p.get('rms')]) for p in
                (source.get('operational_measurements') or {}).get('channels', [])
                if p.get('channel') in (prefix+'A', prefix+'B', prefix+'C')]
    return 1000 if any(_unit(unit) == 'k'+base or (_unit(unit) == base and any(
        _number(value) is not None and abs(value) >= 1000 for value in values)) for unit, values in entries) else 1


def _display_value(value, unit, divisor):
    unit = _unit(unit)
    factor = divisor if unit in ('A', 'V') else 1
    if _number(value) is not None and value != 0 and value/factor == 0:
        factor = 1
    return (_number(value/factor) if _number(value) is not None else None,
            'k'+unit if factor == 1000 else unit)


def _precise(value):
    return str(value) if _number(value) is not None else 'Unavailable'


def _phase_rows(source, quantity, divisor):
    prefix = 'I' if quantity == 'current' else 'V'
    rows, reasons = [], []
    for phase in 'ABC':
        meaning = prefix+phase
        matches = [p for p in source.get('phase_values', []) if p.get('meaning') == meaning]
        withheld = [p for p in source.get('withheld_phases', []) if p.get('meaning') == meaning]
        item = matches[0] if len(matches) == 1 else {}
        missing = item.get('missing_reasons') or {}
        fallback = (withheld[0].get('reason') if withheld else None) or (
            source.get('reason') or ('Phase mapping is ambiguous.' if len(matches) > 1 else 'No uniquely mapped '+quantity+' channel.'))
        label = item.get('label') or item.get('id')
        row = dict(phase=_PHASES[meaning], channel=_text(label, 22) if label != meaning else '', cells=[])
        for region, key in (('pre', 'pre_rms'), ('fault', 'fault_rms'), ('post', 'post_rms')):
            number, unit = _display_value(item.get(key), item.get('units'), divisor)
            reason = missing.get(region) or item.get('reason') or fallback
            reason = _text(reason, 145)
            if number is None and reason not in reasons:
                reasons.append(reason)
            row['cells'].append(dict(value=number, units=unit,
                reason=reason, reason_number=reasons.index(reason)+1 if number is None else None,
                tooltip=(f'{_PHASES[meaning]} · '+(str(label)+' · ' if label and label != meaning else '')
                    +f'{region}: {_precise(item.get(key))} {item.get("units") or "units unavailable"}. '
                    +(item.get('rms_basis') or source.get('rms_basis') or 'Median of complete one-cycle RMS observations in this region.')
                    +' '+str(item.get('scaling_note') or 'Instrument scaling is not independently verified.'))))
        rows.append(row)
    return rows, reasons


def _waveforms(source, quantity, divisor, *, overview=False):
    """Bounded SVG tracks; missing values and source time gaps break paths."""
    channels = []
    originals = list((source.get('groups') or {}).get(quantity) or [])[:3]
    focus = source.get('waveform_focus') or {}
    focused = not overview and focus.get('status') == 'available' and all(isinstance(c.get('focus_trace'), list) for c in originals)
    hover_channels = []
    for channel in originals:
        unit = channel.get('units')
        factor = divisor if _unit(unit) in ('A', 'V') else 1
        retained = channel.get('focus_trace') if focused else channel.get('trace', [])
        trace = [[p[0], p[1], p[2]/factor if _number(p[2]) is not None else p[2]]
                 for p in retained[:4096] if isinstance(p, (list, tuple)) and len(p) >= 3]
        channels.append(dict(channel, units=_display_value(0, unit, divisor)[1], trace=trace))
        hover_channels.append(dict(label=_PHASES.get(channel.get('meaning'), _text(channel.get('label') or channel.get('id'), 80)),
            units=_display_value(0, unit, divisor)[1], original_units=_unit(unit), factor=factor,
            trace=[[p[0], p[1], p[2] if _number(p[2]) is not None else None]
                   for p in retained[:4096] if isinstance(p, (list, tuple)) and len(p) >= 3 and _number(p[1]) is not None]))
    if not channels:
        return None
    width, left, right = 680, 91, 665
    shared = len({_unit(c.get('units')) for c in channels}) == 1
    row_height, top = 42, 8
    height = 180 if shared else top+len(channels)*row_height+29
    all_times = [p[1] for c in channels for p in c.get('trace', [])
                 if isinstance(p, (list, tuple)) and len(p) >= 3 and _number(p[1]) is not None]
    time_range = focus.get('time_range_s') if focused else source.get('time_range_s')
    if (isinstance(time_range, (list, tuple)) and len(time_range) == 2
            and all(_number(v) is not None for v in time_range) and time_range[1] > time_range[0]):
        start, stop = time_range
    elif all_times and max(all_times) > min(all_times):
        start, stop = min(all_times), max(all_times)
    else:
        return None
    time_scale = max(abs(start), abs(stop), 1)
    nstart, nstop = start/time_scale, stop/time_scale
    def x(t):
        ratio = (t/time_scale-nstart)/(nstop-nstart)
        return left+(right-left)*ratio
    out = [f'<svg class="waveform{"" if shared else " waveform-stacked"}" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="{escape(quantity.title())} waveforms in source-local seconds. Gaps remain unknown.">']
    for row, channel in enumerate(channels):
        ytop = 30 if shared else top+row*row_height
        ybottom = 135 if shared else ytop+28
        points = [p for p in channel.get('trace', [])[:4096]
                  if isinstance(p, (list, tuple)) and len(p) >= 3]
        value_points = [p for c in channels for p in c.get('trace', [])[:4096]] if shared else points
        values = [p[2] for p in value_points if isinstance(p, (list, tuple)) and len(p) >= 3 and _number(p[2]) is not None and _number(p[1]) is not None]
        unit = _unit(channel.get('units'))
        label = _PHASES.get(channel.get('meaning'), _text(channel.get('label') or channel.get('id') or 'Unknown phase', 22))
        if shared:
            out.append(f'<text x="{left+20+row*175}" y="14" class="track-label" style="fill:{_COLORS[row]}">{escape(label)}</text>')
            if row == 0:
                out.append(f'<text x="0" y="14" class="track-unit">{escape(unit)}</text>')
        else:
            out.append(f'<text x="0" y="{ytop+12}" class="track-label">{escape(label)}</text>')
            out.append(f'<text x="0" y="{ytop+27}" class="track-unit">{escape(unit)}</text>')
        if not values:
            out.append(f'<text x="{left+8}" y="{ytop+24}">No finite waveform samples available.</text>')
            continue
        extent = max(abs(min(values)), abs(max(values))) or 1
        low, high = -extent, extent
        scale = max(abs(low), abs(high), 1)
        nlow, nhigh = low/scale, high/scale
        def y(v, scale=scale, nlow=nlow, nhigh=nhigh, ytop=ytop, ybottom=ybottom):
            ratio = (v/scale-nlow)/(nhigh-nlow) if nhigh != nlow else .5
            return ybottom-ratio*(ybottom-ytop)
        for kind, color in (() if shared and row else (('pre', '#e9f0f4'), ('fault', '#fde9d9'), ('post', '#e8f1e8'))):
            support = (source.get('region_support') or {}).get(kind) or {}
            bounds = support.get('time_range_s')
            if (isinstance(bounds, (list, tuple)) and len(bounds) == 2
                    and all(_number(t) is not None for t in bounds)):
                a, b = max(start, bounds[0]), min(stop, bounds[1])
                if b > a:
                    out.append(f'<rect x="{x(a):.2f}" y="{ytop}" width="{x(b)-x(a):.2f}" '
                               f'height="{ybottom-ytop}" fill="{color}"/>')
        for value in (() if shared and row else (low, low/2+high/2, high)):
            yy = y(value)
            out.append(f'<line x1="{left}" x2="{right}" y1="{yy:.2f}" y2="{yy:.2f}" class="grid{" zero-line" if value == 0 else ""}"/>')
            out.append(f'<text x="{left-6}" y="{yy+3:.2f}" text-anchor="end" class="axis">{escape(_number(value))}</text>')
        segments, path = [], []
        previous_time = None
        # The producer includes null break markers; explicit source gap intervals
        # also prevent a path from bridging omitted observations.
        gaps = source.get('gaps') or []
        gap_ranges = []
        for gap in gaps if isinstance(gaps, list) else []:
            if isinstance(gap, dict):
                bounds = gap.get('time_range_s') or gap.get('source_range_s')
                if isinstance(bounds, (list, tuple)) and len(bounds) == 2:
                    gap_ranges.append(bounds)
        for point in points:
            _, t, value = point[:3]
            valid = _number(t) is not None and _number(value) is not None and start <= t <= stop
            crosses_gap = valid and previous_time is not None and any(
                _number(a) is not None and _number(b) is not None and previous_time <= b and t >= a
                for a, b in gap_ranges)
            if not valid or crosses_gap:
                if path:
                    segments.append(path)
                    path = []
            if valid:
                path.append((x(t), y(value)))
                previous_time = t
            else:
                previous_time = None
        if path:
            segments.append(path)
        for segment in segments:
            if len(segment) == 1:
                xx, yy = segment[0]
                out.append(f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="1.4" fill="{_COLORS[row]}"/>')
            else:
                coords = ' '.join(f'{xx:.2f},{yy:.2f}' for xx, yy in segment)
                out.append(f'<polyline points="{coords}" fill="none" stroke="{_COLORS[row]}" stroke-width="1.25" stroke-dasharray="{("none", "5 2", "2 2")[row]}"/>')
        if row == len(channels)-1:
            for i in range(5):
                t = start*(1-i/4)+stop*(i/4)
                out.append(f'<text x="{x(t):.2f}" y="{ybottom+15}" text-anchor="middle" class="axis">{escape(_number(t))}</text>')
    out.append(f'<text x="{(left+right)/2}" y="{height-1}" text-anchor="middle" class="axis-title">Source-local time (s)</text></svg>')
    policy = str(focus.get('trace_policy') or 'retained sample envelope') if focused else 'retained sample envelope'
    mode = 'Event detail' if focused else 'Capture overview'
    payload = dict(version=1, range=[start, stop],
        plot=dict(left=left, right=right, top=30 if shared else top, bottom=135 if shared else height-29, width=width, height=height),
        trace_policy=policy, channels=hover_channels,
        digital_inspection=(source.get('digital') or {}).get('inspection') or {},
        record_clock=source.get('record_clock') or dict(
            start_display=(source.get('recorded_times') or {}).get('start') or '',
            trigger_display=(source.get('recorded_times') or {}).get('trigger') or '',
            timezone_label='Not declared', cursor_time_status='unavailable'))
    data = json.dumps(payload, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    scale_note = 'shared phase scale' if shared else 'separate scales for unlike units'
    note = f'{mode} · instantaneous values · {scale_note} · {_number(start)}–{_number(stop)} local s'
    return Markup('<div class="waveform-view" tabindex="0" role="group" aria-label="'+str(escape(quantity.title()+' waveform. '+note))+ '">'
        +'<p class="waveform-caption">'+str(escape(note))+'</p>'+''.join(out)
        +'<div class="waveform-readout" role="status" aria-live="polite">Hover or tap for retained sample values. Arrow keys step through retained samples.</div>'
        +'<script type="application/json" class="waveform-data">'+data+'</script></div>')


def _span_text(value):
    if _number(value) is None or value < 0:
        return 'Unavailable'
    return (_number(value*1000)+' ms') if value < 1 else (_number(value)+' s')


def _signal_rows(digital):
    inspection = digital.get('inspection') or {}
    channels = inspection.get('channels') if isinstance(inspection, dict) else []
    rows = []
    for channel in (channels or [])[:4]:
        if not isinstance(channel, dict):
            continue
        summary = channel.get('window_summary') if isinstance(channel.get('window_summary'), dict) else {}
        raw = summary.get('raw_state_at_start')
        raw_text = ('High (1)' if raw == 1 else 'Low (0)') if type(raw) is int and raw in (0, 1) else 'Unavailable'
        asserted = channel.get('asserted_state')
        reviewed = type(asserted) is int and asserted in (0, 1)
        semantic = summary.get('asserted_at_start')
        state = (('Asserted · ' if semantic else 'Cleared · ')+raw_text
                 if reviewed and raw_text != 'Unavailable' and type(semantic) is bool else raw_text)
        active = summary.get('active_during_window')
        activity = ('Yes' if active else 'No') if reviewed and type(active) is bool else (
            'Polarity unreviewed' if not reviewed else 'Unavailable')
        bounds = summary.get('duration_bounds_s') if reviewed else summary.get('high_duration_bounds_s')
        if isinstance(bounds, (list, tuple)) and len(bounds) == 2 and all(
                _number(value) is not None and value >= 0 for value in bounds) and bounds[1] >= bounds[0]:
            span = _span_text(bounds[0]) if bounds[0] == bounds[1] else _span_text(bounds[0])+'–'+_span_text(bounds[1])
        else:
            value = summary.get('observed_active_span_s') if reviewed else summary.get('observed_high_span_s')
            span = _span_text(value)
            if span != 'Unavailable':
                span = '≥ '+span
        if not reviewed and span != 'Unavailable':
            span = 'High '+span
        partial = bool(summary.get('censored_start') or summary.get('censored_end') or
                       summary.get('gap_count') or summary.get('unknown_samples'))
        rows.append(dict(signal=_text(channel.get('plain_label') or channel.get('label') or channel.get('id') or 'Signal', 52),
            state=state, activity=activity, span=span+(' *' if partial and span != 'Unavailable' else ''),
            reason=_text(summary.get('reason') or channel.get('polarity_label') or 'Recorded indication; physical operation is not established.', 500),
            reviewed=reviewed, partial=partial))
    return rows


def _source(source, index):
    label = source.get('display_label') or source.get('substation') or 'Recording '+str(index+1)
    clock = source.get('record_clock') if isinstance(source.get('record_clock'), dict) else {}
    recorded = source.get('recorded_times') or {}
    result = dict(label=_text(label, 76), record=_text(source.get('record') or 'Source not identified', 100),
        selection=_text(source.get('selection_reason'), 220),
        range=' to '.join(_number(v) or 'unknown' for v in (source.get('time_range_s') or [])),
        rms_basis=_text(source.get('rms_basis') or 'Median of complete one-cycle RMS observations wholly inside each selected region.', 360),
        timing=_text((source.get('timing_evidence') or {}).get('method') or source.get('timing_mode') or 'No event-region selection available', 100),
        insights=_items(source.get('insights'), 2, 170),
        station_device=_text(' / '.join(str(source[k]) for k in ('station', 'device') if source.get(k)), 76),
        start=_text(clock.get('start_display') or recorded.get('start'), 72),
        trigger=_text(clock.get('trigger_display') or recorded.get('trigger'), 72),
        clock_timezone=_text(clock.get('timezone_label') or 'Not declared', 70),
        clock_note=_text(clock.get('cursor_time_reason') or clock.get('reason') or 'Recorder-local date/time; cursor readings use elapsed source time. Clock alignment is unverified.', 150))
    intervals = []
    for kind, name in (('pre', 'before'), ('fault', 'during'), ('post', 'after')):
        support = (source.get('region_support') or {}).get(kind) or {}
        bounds = support.get('time_range_s') or []
        interval = '–'.join(_number(v) or 'unknown' for v in bounds) if len(bounds) == 2 else 'unavailable'
        intervals.append(name+' '+interval)
    result['intervals'] = '; '.join(intervals)
    for quantity in ('current', 'voltage'):
        divisor = _display_scale(source, quantity)
        result[quantity+'_rows'], result[quantity+'_reasons'] = _phase_rows(source, quantity, divisor)
        result[quantity+'_svg'] = _waveforms(source, quantity, divisor)
        group = (source.get('groups') or {}).get(quantity) or []
        has_focus = ((source.get('waveform_focus') or {}).get('status') == 'available'
                     and group and all(isinstance(c.get('focus_trace'), list) for c in group))
        result[quantity+'_overview_svg'] = _waveforms(source, quantity, divisor, overview=True) if has_focus else None
        operational = source.get('operational_measurements') or {}
        prefix = 'I' if quantity == 'current' else 'V'
        measured = [p for p in operational.get('channels', []) if p.get('channel') in (prefix+'A', prefix+'B', prefix+'C')]
        native = []
        for p in measured:
            value, unit = _display_value(p.get('rms'), p.get('unit'), divisor)
            if value is not None:
                native.append(_PHASES[p['channel']]+': '+value+' '+unit)
        window = operational.get('window') or {}
        bounds = [_number(window.get(k)) for k in ('start_s', 'end_s')]
        result[quantity+'_native'] = '; '.join(native)
        result[quantity+'_native_window'] = ' to '.join(bounds)+' s' if all(v is not None for v in bounds) else ''
        reason = operational.get('reason') or 'No stored native fault-window sample RMS is available.'
        if operational.get('status') == 'stored' and not native:
            statuses = list(dict.fromkeys(str(p.get('status') or 'unavailable') for p in measured))
            reason = ('No usable stored '+quantity+' RMS: '+', '.join(statuses)+'.') if statuses else 'No stored '+quantity+' channels are available.'
        result[quantity+'_native_reason'] = _text(reason, 140)
    digital = source.get('digital') or {}
    events = digital.get('events') or []
    result['signal_rows'] = _signal_rows(digital)
    inspection = digital.get('inspection') or {}
    window = inspection.get('time_range_s') if isinstance(inspection, dict) else None
    if not window and result['signal_rows']:
        channels = inspection.get('channels') or []
        window = ((channels[0].get('window_summary') or {}).get('time_range_s')) if channels else None
    result['signal_window'] = ('–'.join(_number(value) or 'unknown' for value in window)+' local s'
        if isinstance(window, (list, tuple)) and len(window) == 2 else 'Unavailable')
    total_signals = inspection.get('total_channels') if isinstance(inspection, dict) else None
    result['signal_channel_note'] = (str(len(result['signal_rows']))+' of '+str(total_signals)+' digital channels shown.'
        if type(total_signals) is int and total_signals > len(result['signal_rows']) else '')
    result['signal_partial'] = any(row['partial'] for row in result['signal_rows'])
    result['signal_unreviewed'] = any(not row['reviewed'] for row in result['signal_rows'])
    result['signal_missing_note'] = 'No bounded during-event sample interval is available.' if (
        result['signal_rows'] and result['signal_window'] == 'Unavailable') else ''
    result['signal_missing_note'] += ' '+_text((digital.get('sequence_signals') or {}).get('missing_note'), 140)
    result['events'] = []
    assumed_polarity = False
    for event in events[:4]:
        local = _number(event.get('source_s'))
        time = (local+' s') if local is not None else 'Time unavailable'
        state = (event.get('kind') or 'Recorded change') if event.get('interpretation_available') is True else 'State change'
        if event.get('kind') == 'state difference across gap':
            bounds = event.get('source_bracket_s') or []
            time = '–'.join(_number(v) or 'unknown' for v in bounds)+' s' if len(bounds) == 2 else 'Time unknown'
            state = 'Across gap; time unknown'
        elif event.get('assertion_source') == 'assumed high state' and state in ('asserted', 'cleared'):
            assumed_polarity = True
            state = 'High state*' if state == 'asserted' else 'Low state*'
        result['events'].append(dict(time=time,
            signal=_text(event.get('plain_label') or _SIGNALS.get(event.get('meaning')) or event.get('label') or event.get('id') or 'Unlabelled signal', 68),
            state=_text(state, 32), unknown_meaning=not bool(event.get('meaning'))))
    result['polarity_note'] = '* High state is assumed active; signal polarity is unverified.' if assumed_polarity and not result['signal_rows'] else ''
    total = digital.get('total_events', len(events))
    result['event_count'] = total if type(total) is int and total >= 0 else len(events)
    result['event_omitted'] = max(0, result['event_count']-(0 if result['signal_rows'] else len(result['events'])))
    initial_active = [v for v in digital.get('insights', []) if 'already active at capture start' in v]
    result['digital_note'] = _text(initial_active[0], 180) if initial_active and not result['signal_rows'] else ''
    result['digital_empty_reason'] = _text(source.get('reason') or (
        'No digital channels were recorded; trip and close outcomes are unknown.' if digital.get('channel_count') == 0
        else 'No recorded digital changes are available in this selection. Constant or unknown signals do not establish whether equipment operated.'), 220)
    return result


def render_incident_report(model):
    """Render one self-contained four-page HTML report without changing ``model``."""
    if not isinstance(model, dict):
        raise TypeError('The incident report model must be an object.')
    sources = model.get('sources') or []
    summary = model.get('summary') or {}
    if not isinstance(summary, dict):
        summary = dict(text=str(summary))
    location = model.get('location') or {}
    generation = model.get('generation') or {}
    classification = summary.get('classification') or {}
    if not isinstance(classification, dict):
        classification = dict(label=str(classification))
    location_number = _number(location.get('km_from_S'))
    has_location = location_number is not None and bool(location.get('method'))
    attachments = [a for a in model.get('attachments') or [] if a.get('status') != 'included']
    report = dict(version=model.get('version', 1), title=_text(model.get('title') or 'Incident report', 90),
        interaction=Markup(Path(__file__).with_name('incident_interaction.js').read_text(encoding='utf-8')),
        incident=_text(model.get('incident_id') or 'Not supplied', 72), revision=model.get('revision', 'Not supplied'),
        generated=_text(generation.get('created_at') or model.get('created_at') or 'Saved generation', 70),
        timezone=_text(generation.get('timezone'), 40),
        headline=_text(summary.get('headline') or 'What the recordings show', 160),
        summary=_text(summary.get('text') or 'Available observations are shown below; missing evidence is identified explicitly.', 650),
        classification=_text(classification.get('label') or classification.get('status') or 'Not established', 100),
        classification_reason=_text(classification.get('reason'), 220),
        location_value=(location_number+' km') if has_location else 'Not available',
        location_reference=_text(location.get('reference_label') or 'Reference end S', 80),
        location_method=_text(location.get('method') if has_location else '', 100),
        location_caveats=_items(location.get('caveats'), 2, 170),
        location_reason=_text(location.get('reason') or location.get('text') or 'No eligible method-labelled fault-location estimate was supplied.', 1000),
        line_diagram=line_diagram_view(model.get('line_diagram')),
        sources=[_source(source, i) for i, source in enumerate(sources[:2])],
        sequence_note=_text((model.get('capture_sequence') or {}).get('note'), 350),
        omitted_sources=max(0, len(sources)-2), attachment_count=len(attachments),
        attachment_notes=_items([str(a.get('record', 'Recording'))+': '+str(a.get('reason') or a.get('status') or 'Attached evidence') for a in attachments], 2, 190),
        findings=_items(model.get('findings'), 3, 210),
        next_steps=_items(model.get('next_steps') or ['Review the missing evidence named in this report before making an operational decision.'], 4, 220),
        limitations=_items(summary.get('limitations'), 3, 220),
        notes=_items(model.get('notes'), 2, 200),
        glossary=[dict(term=_text(g.get('term'), 32), meaning=_text(g.get('meaning'), 180)) for g in (model.get('glossary') or [])[:5]])
    for index, source in enumerate(report['sources']):
        row = next((r for r in (model.get('capture_sequence') or {}).get('captures', [])[:2] if r.get('record') == sources[index].get('record')), {})
        source.update(sequence_order=row.get('order'), capture_first=_text(row.get('first_local_iso'), 40).replace('T', ' '), capture_last=_text(row.get('last_local_iso'), 40).replace('T', ' '))
    report['has_signal_rows'] = any(source['signal_rows'] for source in report['sources'])
    env = Environment(loader=FileSystemLoader(Path(__file__).parent), autoescape=select_autoescape(['html']))
    return env.get_template('incident_summary.html').render(report=report)
