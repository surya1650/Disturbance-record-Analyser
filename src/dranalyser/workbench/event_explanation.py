"""Short explanations of existing observations, never new fault/operation maths."""
import math


def explain_event(ends, distance, *, fault_type=None):
    observations = []
    limits = [
        'Source-local sample times do not establish synchronization between ends.',
        'Recorded engineering units and declared CT/VT scaling are not independent field verification.',
        'Trip and close commands do not establish physical opening or successful reclosure. Actual settings and suitable feedback are required for a protection pass/fail verdict.',
    ]
    for end, report in ends.items():
        regions = {kind: report.get(kind) for kind in ('pre', 'fault', 'post')}
        provenance = dict(end=end, record=report['record'], source_sha256=report['source_sha256'],
                          regions=regions, region_support=report.get('region_support', {}), time_basis=report['time_basis'])
        for quantity, prefix in (('Voltage', 'V'), ('Current', 'I')):
            values = [p for p in report['phase_values'] if p['meaning'].startswith(prefix)
                      and p['pre_rms'] is not None and p['fault_rms'] is not None]
            if not values:
                limits.append(end+': '+quantity.lower()+' change needs complete pre-fault and fault-cycle support; no healthy baseline is invented.')
                continue
            descriptions = []
            channels = []
            for value in values:
                change = value['change_percent']
                direction = 'rose' if value['fault_rms'] > value['pre_rms'] else 'fell' if value['fault_rms'] < value['pre_rms'] else 'was unchanged'
                percent = f' ({change:+.3g}%)' if change is not None and math.isfinite(change) else ''
                descriptions.append(value['meaning']+' '+direction+percent+' ['+value['units']+']')
                channels.append(value['id'])
            observations.append(dict(kind='analog', quantity=quantity.lower(), channels=channels,
                text=end+': recorded '+quantity.lower()+'-channel RMS — '+', '.join(descriptions)+'.', **provenance))
        digital = report['digital']
        for group, meanings in (
            ('trip indication', {'TRIP', 'TRIP_A', 'TRIP_B', 'TRIP_C', 'TRIP_3P', 'TRIP_Z2', 'TRIP_Z3', 'TRIP_Z4'}),
            ('pole/open feedback indication', {'CB_OPEN_A', 'CB_OPEN_B', 'CB_OPEN_C', 'ANY_POLE_DEAD', 'ALL_POLE_DEAD'}),
            ('AR indication', {'AR_INITIATE', 'AR_IN_PROGRESS', 'AR_CLOSE', 'AR_LOCKOUT', 'AR_BLOCK', 'AR_FAIL'}),
        ):
            events = [event for event in digital['events'] if event['interpretation_available']
                      and event['kind'] == 'asserted' and set(event['meaning'].split(', ')) & meanings]
            if events:
                observations.append(dict(kind='digital', text=end+': '+group+' asserted in the recorded sample brackets.',
                    events=[{key: event[key] for key in ('id', 'meaning', 'index', 'sample_bracket', 'source_s', 'source_bracket_s', 'asserted_state', 'assertion_source')} for event in events[:16]], **provenance))
            elif group == 'pole/open feedback indication':
                limits.append(end+': no interpreted pole/open assertion establishes an opening time in this capture.')
        if digital.get('omitted_events'):
            limits.append(end+': the short report omits additional digital transitions; inspect technical evidence for the full timeline.')
    interpretation = []
    if fault_type and distance.get('method') and distance.get('km_from_S') is not None:
        interpretation.append(dict(kind='fault_type', text='The matching operational study classifies '+str(fault_type)+'.',
            fault_type=fault_type, source='Stored operational study; not inferred from RMS changes or relay flags.'))
    else:
        limits.append('A probable fault type is not established by these RMS changes alone.')
    if distance.get('method') and distance.get('km_from_S') is not None:
        interpretation.append(dict(kind='location', text=f"{distance['km_from_S']:.5g} km from S by {distance['method']}; conditional on the stored source and line evidence.",
            method=distance['method'], reference='S', source_records=distance.get('source_records', {})))
    else:
        limits.append('No eligible method-labelled fault distance is available for these selected recordings.')
    return dict(version=1, title='What the recordings show', observations=observations,
        interpretation=interpretation, uncertainty=list(dict.fromkeys(limits)),
        authorizes_location=False, protection_verdict='Not assessed against actual settings and scheme evidence.')


def visual_context(facts, result, selected):
    """Reuse frozen line and navigator availability; do not synthesize geometry."""
    records = [item['file'] for item in result.get('relay_evidence', [])
               if item.get('status') == 'analysed' and item.get('file') in selected.values()]
    return dict(
        line={key: facts.get(key) for key in ('id', 'name', 'length_km', 'terminals', 'sections', 'sha256', 'parameter_status', 'provenance')},
        navigation=dict(available=bool(result.get('navigator_path') and records), records=records,
            note='Stored operational source/R-X views retain their reviewed mappings and supported windows. Display choices do not recalculate them.'))
