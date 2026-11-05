"""One readable incident model from frozen source observations and stored results.

This adapter neither runs a location estimator nor changes source bytes, ratios,
polarity, clocks or operational windows. Display recordings are not physical ends.
"""
from __future__ import annotations

from bisect import bisect_right
import copy
import hashlib
import json
import math
from pathlib import Path

from . import event_study
from .location_summary import public
from .source_diagnostics import _prepared
from .source_snapshot import line_facts
from .record_names import saved_display_name
from .incident_line import build_line_diagram
from .incident_report_classification import stored_source_classification
from .incident_report_focus import attach_waveform_focus
from .incident_report_digital import attach_digital_inspection
from .incident_report_time import recorded_clock
from ..rules.signals import CANONICAL, map_signals

VERSION = 1
RMS_BASIS = ('Median of complete trailing one-cycle sample RMS observations wholly '
             'inside each selected region; includes DC and harmonics. This differs '
             'from native fault-window sample RMS in the stored operational evidence.')


def render_incident_report(model):
    """Render a frozen reader model through the workbench presentation boundary.

    Application persistence consumes this service; report code remains a pure
    presentation consumer and cannot become a dependency of the numerical stack.
    """
    from ..report.incident_summary import render_incident_report as render
    return render(model)


def _inventory(revision):
    return [item for item in (revision.get('bundle') or {}).get('files', [])
            if item.get('kind') == 'comtrade']


def _reviewed_copies(root, revision, inventory):
    """Trust only an explicit, hash-checked instrument-review relation."""
    files = {item['name']: item for item in revision.get('files', [])}
    allowed = (Path(root) / 'runs' / revision['incident_id'] / str(revision['number'])).resolve()
    folder = Path((revision.get('bundle') or {}).get('root', '')).resolve()
    if not folder.is_relative_to(allowed):
        return {}
    names = {item['name'] for item in inventory}
    relations = {}
    for item in inventory:
        name = item['name']
        manifest_name = str(Path(name).parent / 'instrument-review.json')
        entry = files.get(manifest_name)
        if not entry:
            continue
        path = (folder / manifest_name).resolve()
        if not path.is_relative_to(folder) or not path.is_file() or path.stat().st_size > 1048576:
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Instrument review checksum differs from the frozen revision.')
        try:
            manifest = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            continue
        original = manifest.get('original_file') if isinstance(manifest, dict) else None
        if (original not in names or manifest.get('samples_changed') is not False
                or manifest.get('clock_changed') is not False
                or manifest.get('original_files_unchanged') is not True):
            continue
        original_item = next(row for row in inventory if row['name'] == original)
        paths = [original] + ([original_item['data_file']] if original_item.get('data_file') else [])
        hashes = {Path(n).name: files[n]['sha256'] for n in paths if n in files}
        if hashes and hashes == manifest.get('original_sha256'):
            relations[name] = original
    return relations


def _selection(root, revision, records):
    inventory = _inventory(revision)
    by_name = {item['name']: item for item in inventory}
    if records is not None and (not isinstance(records, list) or not 1 <= len(records) <= 2
            or any(not isinstance(n, str) or n not in by_name for n in records)
            or len(set(records)) != len(records)):
        raise ValueError('Select one or two different recordings from this incident revision.')
    reviewed = _reviewed_copies(root, revision, inventory)
    used = (revision.get('result') or {}).get('used') or {}
    primaries = [used[end] for end in ('S', 'R') if used.get(end) in by_name]
    order = list(records) if records is not None else primaries or [item['name'] for item in inventory]
    preferred = {}
    for reviewed_name, original in reviewed.items():
        preferred.setdefault(original, reviewed_name)
    if records is None and not primaries:
        # Stop decoding once two recoverable captures are found. Other sources
        # remain explicit attachments; the report does not inspect every relay.
        recoverable, unavailable, examined = [], [], set()
        for name in order:
            replacement = preferred.get(name, name)
            capture = reviewed.get(replacement, replacement)
            duplicate = by_name[replacement].get('duplicate_of') or capture
            if capture in examined or duplicate in examined:
                continue
            examined.update((capture, replacement, duplicate))
            source, _ = event_study._source(root, revision, replacement)
            (recoverable if source.get('axis', {}).get('elapsed_s') else unavailable).append(name)
            if len(recoverable) == 2:
                break
        order = recoverable + unavailable
    selected, seen, reasons = [], set(), {}
    # Explicit reviewed copies are kept, otherwise prefer the first frozen review.
    for name in order:
        replacement = preferred.get(name, name) if records is None else name
        capture = reviewed.get(replacement, replacement)
        item = by_name[replacement]
        duplicate = item.get('duplicate_of') or capture
        if capture in seen or duplicate in seen:
            continue
        selected.append(replacement)
        seen.update((capture, replacement, duplicate))
        reasons[replacement] = ('Reviewed copy of ' + name + '; same physical capture, user-declared ratings.'
            if replacement != name else 'Explicit report selection.' if records is not None
            else 'Primary recording used by the stored incident analysis.' if name in primaries
            else 'Representative attached recording; physical end is not assigned by this selection.')
        if len(selected) == 2:
            break
    return inventory, selected, reasons, reviewed


def _saved_choice(saved, record, source):
    if not isinstance(saved, dict) or type(saved.get('version')) is not int or saved['version'] < 1:
        return None, ''
    ends = (saved.get('inputs') or {}).get('ends') or {}
    bindings = saved.get('bindings') or saved.get('source_bindings') or {}
    for end, choice in ends.items():
        if isinstance(choice, dict) and choice.get('record') == record:
            if bindings.get(end) == source.get('source_sha256'):
                return copy.deepcopy(choice), 'Saved source-bound observation choices.'
            return None, 'Saved observation choices were withheld because their source hashes differ.'
    return None, ''


def _missing_reason(source, chosen, row, kind):
    field = {'pre': 'pre_rms', 'fault': 'fault_rms', 'post': 'post_rms'}[kind]
    if row.get(field) is not None:
        return ''
    if not chosen.get(kind):
        if kind == 'pre':
            return 'No supported before-event interval; a healthy baseline is not established.'
        if kind == 'post':
            return 'No supported after-event interval within this capture.'
        return 'No supported during-event interval was selected.'
    frequency = source.get('nominal_frequency_hz')
    if type(frequency) not in (int, float) or not math.isfinite(frequency) or not 40 <= frequency <= 70:
        return 'A known 40–70 Hz nominal frequency is required for one-cycle RMS.'
    return 'No complete known one-cycle RMS observation fits wholly inside this interval; it may be too short or contain gaps.'


def _operational(revision, record, mappings_agree):
    """Reuse the existing phase_measurements result, never a new fault-window fit."""
    rows = [row for row in (revision.get('result') or {}).get('relay_evidence', [])
            if row.get('file') == record and row.get('status') == 'analysed']
    if len(rows) != 1 or not isinstance(rows[0].get('measurements'), dict):
        return dict(status='unavailable', reason='No stored native fault-window measurements for this recording.',
                    basis='Native selected fault-window sample-weighted RMS; includes DC and harmonics.', channels=[])
    if not mappings_agree:
        return dict(status='withheld', reason='Observation channel choices differ from the stored operational mappings.',
                    basis='Native selected fault-window sample-weighted RMS; includes DC and harmonics.', channels=[])
    measurements = copy.deepcopy(rows[0]['measurements'])
    return dict(status='stored', reason='Stored operational phase measurements; separate window and RMS basis.',
                basis='Native selected fault-window sample-weighted RMS; includes DC and harmonics.', **measurements)


def _mappings_agree(source, item, chosen):
    default, _, _, digital, _ = _prepared(source, item, dict(voltage_kv=0, mappings={}))
    display, _, _, selected, _ = _prepared(source, item, dict(voltage_kv=0, mappings=chosen['mappings']))
    default_meanings = {c['key']: c.get('meaning', '') for c in default['channels']}
    display_meanings = {c['key']: c.get('meaning', '') for c in display['channels']}
    def digital_meanings(mappings):
        values = {}
        for channel in source['digital']:
            key, label = channel['key'], channel['label']
            automatic = map_signals([label])
            target = mappings.get(key)
            values[key] = ([target] if target != 'ignore' else []) if target else [
                meaning for meaning in CANONICAL if label in automatic.channels(meaning)]
        return values
    return (default_meanings == display_meanings and digital_meanings(digital) == digital_meanings(selected)
            and not any(value != 1 for value in chosen['asserted_states'].values()))


def _source_report(root, revision, record, index, selection_reason, event_inputs):
    source, item = event_study._source(root, revision, record)
    saved, note = _saved_choice(event_inputs, record, source)
    choice = saved or dict(record=record, timing_mode='auto')
    choice['substation'] = saved_display_name(revision, record, station=source.get('station', ''),
        explicit=choice.get('substation', ''))[:120]
    base = dict(record=record, display_label=choice['substation'], substation=choice['substation'],
        selection_reason=selection_reason, station=source.get('station', ''), device=source.get('device', ''),
        recorded_times=source.get('recorded_times', {}), record_clock=recorded_clock(source.get('recorded_times')),
        source_sha256=source.get('source_sha256', {}),
        sample_count=source.get('sample_count', 0), nominal_frequency_hz=source.get('nominal_frequency_hz'),
        status='available', reason='', issues=list(source.get('issues', [])),
        observation_inputs_note=note, rms_basis=RMS_BASIS,
        instrument_review=copy.deepcopy(source.get('instrument_review') or {}),
        instrument_review_sha256=source.get('instrument_review_sha256'))
    try:
        # One source is intentionally prepared at a time. This internal slot is
        # never a physical-end declaration and permits same-relay comparisons.
        normalised, prepared = event_study.prepare_inputs(root, revision,
            dict(ends={'S': choice}, same_event_confirmed=False))
        chosen = normalised['ends']['S']
        detail = event_study._end_report(*prepared['S'], chosen)
    except ValueError as exc:
        if 'checksum' in str(exc).lower():
            raise
        base.update(status='unavailable', reason=str(exc), phase_values=[],
            groups=dict(current=[], voltage=[]), digital=dict(events=[], total_events=0, omitted_events=0,
                insights=['Signal interpretation is unavailable because source timing could not be prepared.']),
            region_support=dict(pre=None, fault=None, post=None), time_range_s=None,
            insights=[str(exc)], operational_measurements=_operational(revision, record, False), gaps={})
        return base, False
    base.update(detail)
    base['rms_basis'] = RMS_BASIS
    base['time_basis'] = 'Each recording uses its own source-local seconds. Clocks are not synchronized by this report.'
    for row in base['phase_values']:
        row['phase'] = {'A': 'R', 'B': 'Y', 'C': 'B'}.get(row['meaning'][-1], '')
        row['missing_reasons'] = {kind: _missing_reason(source, chosen, row, kind) for kind in ('pre', 'fault', 'post')}
        row['rms_basis'] = RMS_BASIS
        row['scaling_note'] = ('Primary scale from saved user-declared instrument ratings; original file bytes unchanged, physical accuracy unverified.'
            if row.get('id') in (base['instrument_review'].get('ratios') or {})
            else 'CFG-declared primary scale; instrument/wiring accuracy is not independently verified.'
            if row['units'].startswith(('A', 'V')) else 'Physical scaling is unavailable; values remain in recorded counts.')
    # Include phases that are absent or withheld so no source can silently lose
    # one phase. Missing values always have a named reason.
    present = {row['meaning'] for row in base['phase_values']}
    withheld = {row['meaning']: row['reason'] for row in base.get('withheld_phases', [])}
    for meaning in ('IA', 'IB', 'IC', 'VA', 'VB', 'VC'):
        if meaning not in present:
            reason = withheld.get(meaning, 'No unique mapped ' + meaning + ' channel is available; review channel meanings.')
            base['phase_values'].append(dict(id=None, label=meaning, meaning=meaning,
                phase={'A': 'R', 'B': 'Y', 'C': 'B'}[meaning[-1]], units='unavailable',
                pre_rms=None, fault_rms=None, post_rms=None, pre_windows=0, fault_windows=0, post_windows=0,
                missing_reasons={kind: reason for kind in ('pre', 'fault', 'post')},
                reason=reason, interpretation='Measurement unavailable.', rms_basis=RMS_BASIS))
    times = source['axis']['elapsed_s']
    periods = [b-a for a, b in zip(times, times[1:], strict=False)]
    gap_limit = min(periods)*8 if periods else float('inf')
    breaks = sorted(set(source.get('break_indices', [])) | set(source.get('axis', {}).get('break_indices', []))
        | {i+1 for i, delta in enumerate(periods) if delta > gap_limit})
    # The generic display envelope recognizes time gaps; also insert explicit
    # decode discontinuities so a source break can never become a drawn bridge.
    for group in base['groups'].values():
        for channel in group:
            for field in ('trace', 'rms_trace'):
                points = channel[field]
                if breaks:
                    retained = []
                    cursor = 0
                    for point in points:
                        stop = bisect_right(breaks, point[0], cursor)
                        if stop > cursor:
                            boundary = breaks[cursor]
                            retained.append([boundary, times[boundary], None])
                            cursor = stop
                        retained.append(point)
                    channel[field] = retained
    base['gaps'] = dict(break_indices=breaks[:128], omitted_break_indices=max(0, len(breaks)-128),
        unknown_analog_samples=sum(value is None for c in source['channels'] for value in c['values']),
        note='Unknown observations and timing gaps remain breaks in waveform paths.')
    prepared, _, _, mapped, provenance = _prepared(source, item, dict(voltage_kv=0, mappings=chosen['mappings']))
    attach_waveform_focus(base, prepared, breaks=breaks)
    attach_digital_inspection(base, source, mapped, provenance, chosen['asserted_states'], breaks=breaks)
    agree = _mappings_agree(source, item, chosen)
    base['operational_measurements'] = _operational(revision, record, agree)
    stored_rows = [row for row in (revision.get('result') or {}).get('relay_evidence', [])
                   if row.get('file') == record and row.get('status') == 'analysed']
    base['quality'] = dict(current_transformer_saturation_flagged=any(row.get('ct_saturation') is True for row in stored_rows),
        clipped_channels=sorted({str(channel) for row in stored_rows for channel in row.get('clipped_channels', [])}),
        source_flags=list(item.get('flags', []))[:32])
    # Keep recorded changes literal; a bit change cannot prove physical motion.
    for event in base['digital']['events']:
        event['plain_label'] = _signal_label(event.get('meaning', ''), event.get('label', ''))
        if event['index'] in breaks:
            event.update(kind='state difference across gap', interpretation_available=False,
                observation='Recorded states differ across an unobserved gap; no transition time is established.')
            continue
        event['observation'] = ('Recorded ' + event['kind'] + ' indication under stated polarity.'
            if event.get('interpretation_available') else 'Recorded state change; asserted-state polarity needs review.')
    initial_active = [text for text in base['digital']['insights'] if 'already active at capture start' in text][:4]
    base['digital']['channel_count'] = len(source['digital'])
    base['digital']['unknown_samples'] = sum(value is None for c in source['digital'] for value in c['states'])
    base['digital']['insights'] = initial_active + [
        ('Recorded signal changes are source-local observations. Commands do not prove breaker opening or closure.'),
        ('No digital channels are recorded; trip and close outcomes are unknown.' if not source['digital'] else
         'No signal changes were observed within this capture; missing or unmapped indications remain unknown.'
         if not base['digital']['total_events'] else
         str(base['digital']['total_events']) + ' recorded signal changes; sample brackets limit their timing.')]
    return base, agree


def _signal_label(meaning, original):
    labels = {'START': 'Disturbance start indication', 'TRIP': 'Trip command indication',
              'TRIP_A': 'R-phase trip indication', 'TRIP_B': 'Y-phase trip indication',
              'TRIP_C': 'B-phase trip indication', 'TRIP_3P': 'Three-phase trip indication',
              'AR_CLOSE': 'Automatic reclose command indication', 'AR_INITIATE': 'Automatic reclose initiation indication',
              'AR_BLOCK': 'Automatic reclose blocking indication', 'AR_LOCKOUT': 'Automatic reclose lockout indication',
              'CARRIER_SEND': 'Protection message sent indication', 'CARRIER_RECV': 'Protection message received indication',
              'Z1': 'Protection zone 1 indication', 'Z2': 'Protection zone 2 indication',
              'Z3': 'Protection zone 3 indication', 'Z4': 'Protection zone 4 indication',
              'TRIP_Z2': 'Protection zone 2 trip indication', 'TRIP_Z3': 'Protection zone 3 trip indication',
              'TRIP_Z4': 'Protection zone 4 trip indication'}
    return labels.get(meaning, original or 'Recorded digital signal')


def _analogue_observations(source):
    """Name representative measured changes without interpreting their cause."""
    def number(value):
        if value == 0:
            return '0'
        return (f'{value:,.3f}'.rstrip('0').rstrip('.') if .001 <= abs(value) < 1000000
                else format(value, '.3g'))
    observations = []
    for prefix, quantity, factors in (('I', 'current', {'A': 1, 'kA': 1000}),
                                      ('V', 'voltage', {'V': 1, 'kV': 1000})):
        rows = [row for row in source['phase_values'] if row['meaning'].startswith(prefix)
                and row.get('pre_rms') is not None and row.get('fault_rms') is not None]
        physical = [row for row in rows if row['units'].split(' ', 1)[0] in factors]
        if physical:
            # RMS is nonnegative; logarithms keep the ranking finite even for
            # extreme supported values and compare only compatible quantities.
            def change(row, factors=factors):
                delta = abs(row['fault_rms']-row['pre_rms'])
                return math.log(delta)+math.log(factors[row['units'].split(' ', 1)[0]]) if delta else -math.inf
            chosen = max(physical, key=change)
            original_unit = chosen['units'].split(' ', 1)[0]
            factor = factors[original_unit]
            kilo = max(chosen['pre_rms'], chosen['fault_rms']) >= 1000/factor
            unit = ('k' if kilo else '')+('A' if prefix == 'I' else 'V')
            divisor = (1000 if kilo else 1)/factor
            label = quantity
        elif rows:
            # Counts cannot be ranked against amperes/volts or unlike units.
            # Prefer the largest same-unit set, retaining phase-order ties.
            groups = {}
            for row in rows:
                groups.setdefault(row['units'], []).append(row)
            compatible = max(groups.values(), key=len)
            chosen = max(compatible, key=lambda row: abs(row['fault_rms']-row['pre_rms']))
            unit, label, divisor = chosen['units'], quantity+' channel', 1
        else:
            continue
        observations.append(chosen['phase']+'-phase '+label+' '
            + number(chosen['pre_rms']/divisor)+' → '+number(chosen['fault_rms']/divisor)+' '+unit)
    return observations


def _location(revision, sources, agreements, facts):
    result = revision.get('result') or {}
    used = result.get('used') or {}
    selected = {source['record'] for source in sources}
    stored = facts['location']
    structured = result.get('location_summary')
    reasons = []
    if not structured:
        reasons.append('No source-bound structured operational location is stored for this revision.')
    if not used or set(used.values()) != selected:
        reasons.append('The report recordings do not match the stored operational recording cohort.')
    if not all(agreements):
        reasons.append('Report channel mappings or digital polarity differ from the stored operational choices.')
    if stored.get('overlay_eligible') is not True:
        reasons.append(stored.get('text') or 'The stored location is unavailable or its engineering inputs need review.')
    eligible = bool(structured and used and set(used.values()) == selected and all(agreements)
                    and stored.get('overlay_eligible') is True and stored.get('method'))
    reference = facts.get('terminals', {}).get('S') or 'Sending reference S'
    if reference == 'Not available':
        reference = 'Sending reference S'
    return dict(status='Existing conditional estimate' if eligible else 'unavailable',
        km_from_S=stored.get('km_from_S') if eligible else None,
        km_from_R=stored.get('km_from_R') if eligible else None,
        method=stored.get('method') if eligible else None, reference='S', reference_label=reference,
        mode=stored.get('mode') if eligible else None,
        fault_type=stored.get('fault_type') if eligible else None,
        text=(str(stored.get('km_from_S')) + ' km from ' + reference + ' by ' + stored['method']) if eligible
             else 'Fault distance is unavailable for these report recordings.',
        reason=' '.join(reasons) if reasons else 'Existing method-labelled operational result bound to this revision, source bytes and frozen line model; declared engineering inputs remain conditional.',
        source_records=used, parameter_status=facts.get('parameter_status'), line_sha256=facts.get('sha256'),
        provenance=stored.get('provenance', ''),
        caveats=list(structured.get('caveats') or []) if isinstance(structured, dict) else [],
        diagnostic_interval_km=structured.get('interval_km') if eligible else None,
        interval_kind=structured.get('interval_kind') if isinstance(structured, dict) else None,
        authorizes_location=False)


def build_incident_report(root, revision, *, records=None, event_inputs=None):
    """Build finite JSON for one immutable revision without recomputing physics."""
    inventory, selected, selection_reasons, reviewed = _selection(root, revision, records)
    sources, agreements = [], []
    for index, record in enumerate(selected, 1):
        source, agree = _source_report(root, revision, record, index, selection_reasons[record], event_inputs)
        sources.append(source)
        agreements.append(agree)
    facts = line_facts(root, revision)
    location = _location(revision, sources, agreements, facts)
    line_diagram = build_line_diagram(revision, facts, sources, location)
    changes = [source for source in sources if source.get('fault')]
    classification = dict(status='unavailable', label='Not established',
        reason='Recorded changes alone do not establish the physical fault type.')
    if location.get('fault_type') and str(location['fault_type']).upper() not in ('NONE', 'UNKNOWN', 'UNCLASSIFIED'):
        fault = str(location['fault_type'])
        names = {'AG': 'R phase to earth', 'BG': 'Y phase to earth', 'CG': 'B phase to earth',
                 'AB': 'R–Y phases', 'BC': 'Y–B phases', 'CA': 'B–R phases', 'ABC': 'Three phases',
                 'ABG': 'R–Y phases to earth', 'BCG': 'Y–B phases to earth', 'CAG': 'B–R phases to earth',
                 'ABCG': 'Three phases to earth'}
        classification = dict(status='stored operational classification', label=names.get(fault, fault),
            code=fault, reason='Classification belongs to the eligible stored operational result.')
    if location['km_from_S'] is None:
        classification = stored_source_classification(revision, sources, agreements, facts) or classification
    attachments = []
    for item in inventory:
        name = item['name']
        selected_here = name in selected
        related = reviewed.get(name, name)
        selected_capture = any(reviewed.get(n, n) == related for n in selected)
        status = 'included' if selected_here else 'same-capture attachment' if selected_capture else 'attached; not plotted'
        reason = (selection_reasons[name] if selected_here else 'Another copy of the same capture is represented; it is not counted twice.'
            if selected_capture else item.get('error') or 'The readable report plots at most two representative recordings; this attachment remains in the incident evidence.')
        attachments.append(dict(record=name, status=status, reason=reason, duplicate_of=item.get('duplicate_of') or reviewed.get(name)))
    paired_data = {item.get('data_file') for item in inventory if item.get('data_file')}
    listed = {item['record'] for item in attachments} | paired_data
    bundle_items = {item['name']: item for item in (revision.get('bundle') or {}).get('files', [])}
    for entry in revision.get('files', []):
        name = entry['name']
        if name in listed:
            continue
        item = bundle_items.get(name, {})
        attachments.append(dict(record=name, status='supporting attachment; not plotted',
            kind=item.get('kind', 'supporting file'), source_sha256=entry.get('sha256'),
            reason=item.get('error') or 'Supporting incident file; it is preserved with the frozen revision and is not another waveform capture.'))
    findings = []
    for source in sources:
        if source['status'] != 'available':
            findings.append(source['display_label'] + ': ' + source['reason'])
            continue
        analogue_observations = _analogue_observations(source)
        if analogue_observations:
            findings.append(source['display_label'] + ': Before → during RMS: ' + '; '.join(analogue_observations)+'.')
        quality = source.get('quality') or {}
        if quality.get('current_transformer_saturation_flagged'):
            findings.insert(0, source['display_label'] + ': the stored analysis flags possible current-transformer saturation. Current waveforms may be distorted; review them before relying on the measurements or distance.')
        if quality.get('clipped_channels'):
            findings.insert(0, source['display_label'] + ': the stored analysis flags clipped waveform samples; some recorded peaks may be limited by the recorder.')
        if not source.get('pre'):
            findings.append(source['display_label'] + ': a healthy before-event baseline is not established by the selected support.')
        if not source.get('post'):
            findings.append(source['display_label'] + ': no supported after-event interval is available in this capture.')
        if source['gaps']['unknown_analog_samples'] or source['gaps']['break_indices']:
            findings.append(source['display_label'] + ': missing observations or timing gaps limit the measurements; waveform gaps are retained.')
    if not sources:
        findings.append('No COMTRADE recording is attached to this incident revision.')
    next_steps = []
    if location['km_from_S'] is None:
        next_steps.append('For fault distance, review the line model, physical end assignments, CT/VT ratings and channel meanings, then run the existing fault calculation.')
    if any(not source.get('fault') for source in sources):
        next_steps.append('Review the source waveforms and select a supported during-event interval where automatic timing is unavailable.')
    next_steps.append('Confirm physical breaker movement and the actual fault site using station evidence or field inspection; recorded commands alone do not establish them.')
    text = (str(len(sources)) + ' recording' + ('s are' if len(sources) != 1 else ' is') + ' represented independently. '
        + ('A recorded-change interval is available in ' + str(len(changes)) + ' recording(s). ' if changes else 'A during-event interval is not established by the selected observation support. ')
        + ('An existing ' + location['method'] + ' fault-distance result is available.' if location['km_from_S'] is not None
           else 'A physical fault distance is unavailable for this selection.'))
    return public(dict(version=VERSION, kind='incident-reader-report', title='Incident report',
        incident_id=revision['incident_id'], revision=revision['number'], sources=sources,
        summary=dict(headline='Recorded disturbance review', text=text, classification=classification,
            limitations=['Values describe the captured electrical samples; before/during/after labels refer to selected observation intervals.',
                'Each recording retains its own local clock. This report does not establish physical breaker operation.']),
        location=location, line_diagram=line_diagram, findings=findings, next_steps=next_steps,
        glossary=[dict(term='RMS', meaning='Effective value of a varying signal, calculated from its samples; it includes DC and harmonics.'),
            dict(term='Before / during / after', meaning='Selected recording intervals around the observed change; a missing interval stays unknown.'),
            dict(term='CT / VT', meaning='Instrument transformers that scale current / voltage for the recorder.'),
            dict(term='Recorded indication', meaning='A stored digital state or command, which needs context before a physical action can be confirmed.')],
        attachments=attachments, notes=[RMS_BASIS,
            'A whole-record maximum is never substituted for fault current. RMS is not calculated by dividing a waveform peak by the square root of two.',
            'Source waveforms use decoded CFG-declared units where supported. Raw counts remain counts; declared ratios are not independent field verification.',
            'This incident report uses existing observations and eligible stored operational evidence. It does not recalculate location, repair polarity or align clocks.']))
