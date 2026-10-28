"""Bounded display timelines from original samples; no estimators or clock repair."""
import math

from .source_display import timeline
from .source_inspection import _source, _trace
from .source_snapshot import line_facts

ROLES = ('trip', 'open', 'closed', 'ar_initiate', 'ar_close', 'ar_block', 'ar_lockout')
MAX_RUNS = 2048


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def clean_settings(root, row, raw):
    keys = {'alignment', 'common_event', 'reviewer', 'evidence', 'ends'}
    if not isinstance(raw, dict) or set(raw) != keys or raw['alignment'] not in ('independent', 'reviewed_offsets'):
        raise ValueError('Supply explicit playback ends, alignment mode and review evidence.')
    if type(raw['common_event']) is not bool or not isinstance(raw['ends'], dict) or set(raw['ends'])-{'S', 'R'}:
        raise ValueError('Choose Sending/Receiving records explicitly; confirm the common event when both are selected.')
    cleaned = {key: raw[key] for key in ('alignment', 'common_event')}
    for key in ('reviewer', 'evidence'):
        value = raw[key]
        if not isinstance(value, str) or len(value) > 2000:
            raise ValueError('Review name and evidence must be text of at most 2000 characters.')
        cleaned[key] = value.strip()
    ends, identities = {}, {}
    assigned = row['metadata'].get('assignments', {})
    for end, choice in raw['ends'].items():
        if not isinstance(choice, dict) or set(choice) != {'record', 'offset_ms', 'onset_ms', 'signals_reviewed', 'signals'}:
            raise ValueError('Each end needs a recording, time inputs and reviewed signal selections.')
        name = choice['record']
        if not isinstance(name, str) or name.startswith('@join:'):
            raise ValueError('Select an original capture at each end. Successive same-relay captures are not opposite ends.')
        source, item = _source(root, row, name)
        if item.get('duplicate_of'):
            raise ValueError(name+': a duplicate capture cannot represent an independent end.')
        identities[end] = (source.get('station', '').strip().casefold(), source.get('device', '').strip().casefold())
        declared = assigned.get(name, {}).get('end') or item.get('terminal_end')
        if declared and declared != end:
            raise ValueError(name+': playback end conflicts with the operational assignment.')
        times = source['axis'].get('elapsed_s', [])
        if len(times) < 2 or any(not finite(t) for t in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ValueError(name+': playback requires at least two finite increasing source times; sample inspection remains available.')
        trigger = timeline(source)['trigger_offset_s']
        offset, onset = choice['offset_ms'], choice['onset_ms']
        if not finite(offset) or abs(offset) > 86400000 or (raw['alignment'] == 'independent' and offset != 0):
            raise ValueError('Use finite reviewed offsets within one day, or zero in independent-trigger mode.')
        if onset is not None and (not finite(onset) or trigger is None or not times[0] <= onset/1000+trigger <= times[-1]):
            raise ValueError('Fault reference must be inside this capture in ms from its recorded trigger, or blank.')
        if trigger is None:
            raise ValueError(name+': no usable recorded trigger reference; use sample inspection.')
        display = [(t-trigger)*1000+offset for t in (times[0], times[-1])]
        if any(not finite(t) for t in display) or not finite(display[1]-display[0]) or display[1] <= display[0]:
            raise ValueError(name+': playback coordinates exceed a finite representable millisecond range.')
        signals = choice['signals']
        if not isinstance(signals, dict) or set(signals)-set(ROLES) or type(choice['signals_reviewed']) is not bool:
            raise ValueError('Choose explicit contact/command channels and review their meanings and polarity.')
        known = {c['key'] for c in source['digital']}
        for role, signal in signals.items():
            if (not isinstance(signal, dict) or set(signal) != {'id', 'active'} or not isinstance(signal['id'], str) or signal['id'] not in known
                    or type(signal['active']) is not int or signal['active'] not in (0, 1)):
                raise ValueError(role+': select an existing digital ID and explicit active state 0 or 1.')
        if len({v['id'] for v in signals.values()}) != len(signals):
            raise ValueError('Use distinct channels for commands and contacts. One channel cannot prove several physical states.')
        if signals and not choice['signals_reviewed']:
            raise ValueError(name+': confirm signal meanings and polarity before timing/position interpretation.')
        ends[end] = dict(choice, source_sha256=source['source_sha256'])
    if not ends or len({v['record'] for v in ends.values()}) != len(ends):
        raise ValueError('Choose one or two distinct original recordings; do not reuse one capture at both ends.')
    generic = {'', 'unknown', 'station', 'relay', 'ied', 'none', '0'}
    if len(ends) == 2 and identities['S'] == identities['R'] and all(v not in generic for v in identities['S']):
        raise ValueError('Both headers declare the same station and relay. Review identity or combine successive captures; do not present them as opposite ends.')
    if len(ends) == 2 and not raw['common_event']:
        raise ValueError('Confirm that these recordings belong to opposite ends of the same event.')
    if (raw['alignment'] == 'reviewed_offsets' or len(ends) == 2 or any(v['signals'] or v['onset_ms'] is not None for v in ends.values())) and not (cleaned['reviewer'] and cleaned['evidence']):
        raise ValueError('Provide reviewer and evidence for end identity, contact mapping, fault references and alignment declarations.')
    cleaned['ends'] = ends
    return cleaned


def signal_timeline(states, times, active, breaks=()):
    """Held sample states stop at gaps; initial/gap assertions have unknown onset."""
    gap = min(b-a for a, b in zip(times, times[1:], strict=False))*8
    boundaries = set(breaks)
    runs, edges = [], []
    start = 0
    for i in range(1, len(times)):
        split = i in boundaries or times[i]-times[i-1] > gap
        if split or states[i] != states[i-1]:
            runs.append([times[start], times[i-1] if split else times[i], states[i-1]])
            if not split and states[i-1] in (0, 1) and states[i] == active and states[i-1] != active:
                edges.append(dict(at_s=times[i], bracket_s=[times[i-1], times[i]], index=i))
            start = i
        if len(runs) > MAX_RUNS or len(edges) > MAX_RUNS:
            return dict(runs=[], edges=[], status='unavailable', reason='More than 2048 state runs/edges; no truncated signal is treated as continuous.')
    if len(runs) >= MAX_RUNS:
        return dict(runs=[], edges=[], status='unavailable', reason='State-run display budget exceeded; continuity withheld.')
    runs.append([times[start], times[-1], states[-1]])
    return dict(runs=runs, edges=edges, status='available', reason='Held recorded states; transitions lie between adjacent samples. Gaps and capture boundaries stay unknown.')


def duration(first, second):
    if first is None or second is None:
        return None
    return dict(ms=(second['at_s']-first['at_s'])*1000,
                sample_bracket_ms=[(second['bracket_s'][0]-first['bracket_s'][1])*1000,
                                   (second['bracket_s'][1]-first['bracket_s'][0])*1000])


def record_playback(root, row, end, choice):
    source, _ = _source(root, row, choice['record'])
    if source['source_sha256'] != choice['source_sha256']:
        raise ValueError('Playback source changed. Review these original inputs again.')
    times = source['axis']['elapsed_s']
    signals = {}
    for role, selected in choice['signals'].items():
        channel = next(c for c in source['digital'] if c['key'] == selected['id'])
        signals[role] = dict(id=channel['key'], label=channel['label'], active=selected['active'],
                            **signal_timeline(channel['states'], times, selected['active'], source.get('break_indices', [])))
    evidence = next((r for r in (row.get('result') or {}).get('relay_evidence', []) if r['file'] == choice['record'] and r.get('status') == 'analysed'), {})
    trigger = timeline(source)['trigger_offset_s']
    onset = choice['onset_ms']/1000+trigger if choice['onset_ms'] is not None else evidence.get('inception_local_s')
    if not finite(onset) or not times[0] <= onset <= times[-1]:
        onset = None
    reference = dict(at_s=onset, bracket_s=[onset, onset]) if onset is not None else None
    def first(role, after=None):
        return next((e for e in signals.get(role, {}).get('edges', []) if after is None or e['at_s'] >= after), None)
    trip = first('trip', onset)
    opened = first('open', trip['at_s'] if trip else onset)
    closed = first('closed', opened['at_s']) if opened else None
    ar_close = first('ar_close', opened['at_s'] if opened else onset)
    timings = dict(fault_to_trip=duration(reference, trip), trip_to_open=duration(trip, opened),
                   open_to_closed=duration(opened, closed), open_to_ar_command=duration(opened, ar_close))
    cycles = []
    opens = signals.get('open', {}).get('edges', [])
    for i, opening in enumerate(opens[:64]):
        ceiling = opens[i+1]['at_s'] if i+1 < len(opens) else math.inf
        def within(role, opening=opening, ceiling=ceiling):
            return next((e for e in signals.get(role, {}).get('edges', []) if opening['at_s'] <= e['at_s'] < ceiling), None)
        closure, command = within('closed'), within('ar_close')
        retrip = next((e for e in signals.get('trip', {}).get('edges', []) if closure is not None and closure['at_s'] < e['at_s'] <= ceiling), None)
        cycles.append(dict(sequence=i+1, open_s=opening['at_s'], closed_s=closure['at_s'] if closure else None,
                           ar_command_s=command['at_s'] if command else None,
                           open_to_closed=duration(opening, closure), open_to_ar_command=duration(opening, command),
                           closed_to_retrip=duration(closure, retrip)))
    analog = [dict(id=c['key'], label=c['label'], units=c['units'], trace=_trace(c['values'], times, 300)) for c in source['channels'][:6]]
    events = [dict(e, role=role, channel=s['id']) for role, s in signals.items() for e in s['edges']]
    if reference:
        events.append(dict(reference, role='fault_reference', channel='', index=None))
    return dict(end=end, file=choice['record'], source_sha256=source['source_sha256'],
                capture_s=[times[0], times[-1]], trigger_s=trigger, offset_ms=choice['offset_ms'],
                onset_s=onset, onset_basis='operator-declared reference' if choice['onset_ms'] is not None else 'existing operational inception' if onset is not None else 'not supplied',
                signals=signals, timings=timings, ar_sequences=cycles, omitted_ar_sequences=max(0, len(opens)-64), events=sorted(events, key=lambda e: (e['at_s'], e['role'])),
                analog=analog, analog_omitted=max(0, len(source['channels'])-6),
                note='Display only. Contact indications are not independently verified mechanical positions. Initial active states have unknown onset; commands do not prove contact movement.')


def playback_data(root, row, settings):
    line = line_facts(root, row)
    return dict(revision=row['number'], settings=settings, records=[record_playback(root, row, e, c) for e, c in settings['ends'].items()],
                line=line, location_text=(row.get('result') or {}).get('location_text', 'Location unavailable; operational prerequisites not supplied.'),
                alignment_note='Independent times relative to each relay trigger; no cross-end event ordering is established.' if settings['alignment'] == 'independent' else 'Shared display axis uses reviewer-declared offsets. This does not authorize synchronized estimators or verify clock accuracy.',
                authorizes_location=False, alignment_eligible=False)
