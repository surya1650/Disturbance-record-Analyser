"""Traceable stage observations and pair candidates; never alignment or verdicts."""
from __future__ import annotations

from collections import Counter
from itertools import product

from ..dsp.measurements import relative_ms
from ..dsp.stages import phase_stages
from ..dsp.stage_windows import stage_window

MARKERS = ('START', 'TRIP', 'TRIP_A', 'TRIP_B', 'TRIP_C', 'TRIP_3P', 'AR_CLOSE',
           'AR_INITIATE', 'AR_LOCKOUT', 'CB_OPEN_A', 'CB_OPEN_B', 'CB_OPEN_C',
           'ANY_POLE_DEAD', 'ALL_POLE_DEAD')


def stage_evidence(an, signals, trigger):
    out = phase_stages(an)
    out['markers'] = [{'signal': s['signal'], 'mapping_state': s['state'], 'channel': p['channel'],
                       'state': p['state'], 'intervals': p['intervals'],
                       'assertions_s': p['assertions_s'], 'initially_active': p['initially_active']}
                      for s in signals if s['signal'] in MARKERS for p in s['points']]
    closes = [(t, m['channel']) for m in out['markers'] if m['signal'] == 'AR_CLOSE'
              and m['mapping_state'] == 'assertion observed' and not m['initially_active']
              for t in m['assertions_s']]
    prior_active_end = None
    for stage in out['intervals']:
        stage['estimation_window'] = stage_window(an, stage)
        stage['start_trigger_ms'] = relative_ms(stage['start_s'], trigger)
        stage['end_trigger_ms'] = relative_ms(stage['end_s'], trigger)
        stage['reclose_evidence'] = []
        if stage['stable'] and stage['phase_pattern']:
            if stage['kind'] == 'renewed current candidate' and prior_active_end is not None:
                stage['reclose_evidence'] = [{'channel': channel, 'assertion_s': t} for t, channel in closes
                                            if prior_active_end <= t <= stage['start_boundary_range_s'][1]]
                if stage['reclose_evidence']:
                    stage['kind'] = 'reclose candidate'
            prior_active_end = stage['end_s']
    out['mapping_snapshot'] = an.record.notes.get('channel_mapping', {})
    out['analysis_window_relation'] = 'not assessed'
    if out['status'] == 'observed':
        overlap = [s for s in out['intervals'] if s['start_s'] < an.window.t_end and s['end_s'] > an.window.t_start]
        out['analysis_window_relation'] = ('multiple or uncertain observation intervals; review analytical window'
            if len(overlap) != 1 or not overlap[0]['stable'] or not overlap[0]['phase_pattern']
            else 'one current-pattern interval; physical stage validity is not established')
    return out


def compare_stages(left, right, onset_association):
    """Keep every candidate alternative; never pair by ordinal or trigger zero."""
    out = {'version': 1, 'status': 'unavailable', 'reason': '', 'pairs': [], 'applied': False,
           'confirmed': False, 'basis': 'independent local seconds; no clock offset applied',
           'left_record_hash': left.get('record_hash'), 'right_record_hash': right.get('record_hash'),
           'requirements': ['Reviewed line/circuit and relay identity', 'Source-bound same-stage confirmation',
                            'Independent timing evidence with supported uncertainty before common event ordering']}
    a, b = left.get('stages', {}), right.get('stages', {})
    if a.get('status') != 'observed' or b.get('status') != 'observed':
        out['reason'] = 'A local stage inventory is unavailable; review the per-record refusal.'
        return out
    if (not left.get('record_hash') or not right.get('record_hash') or
            a.get('record_hash') != left['record_hash'] or b.get('record_hash') != right['record_hash'] or
            a.get('mapping_snapshot') != left.get('channel_mapping', {}) or
            b.get('mapping_snapshot') != right.get('channel_mapping', {})):
        out['reason'] = 'Missing or stale record hash/mapping provenance.'
        return out
    if any(inv.get('quality_reasons') and not any(s.get('estimation_window', {}).get('status') == 'eligible'
                                               for s in inv['intervals']) for inv in (a, b)):
        out['reason'] = 'Input quality withholds stage association; local observations are retained.'
        return out
    if left['end'] == right['end'] and {left.get('protection_system'), right.get('protection_system')} != {'Main-1', 'Main-2'}:
        out['reason'] = 'A same-terminal Main-1/Main-2 identity pair is not established.'
        return out
    active = [[s for s in inv['intervals'] if s['stable'] and s['phase_pattern']] for inv in (a, b)]
    if not all(active):
        out['reason'] = 'No stable elevated phase-current interval at one or both relays.'
        return out
    if len(active[0])*len(active[1]) > 256:
        out['reason'] = 'Candidate-pair limit exceeded; no partial association matrix published.'
        return out
    counts = [Counter(s['phase_pattern'] for s in stages) for stages in active]
    groups = [inv.get('reviewed_groups', {}) if inv.get('review_status') == 'valid reviewer declaration' else {}
              for inv in (a, b)]
    for x, y in product(*active):
        pattern = x['phase_pattern']
        quality = all(not inv.get('quality_reasons') or s.get('estimation_window', {}).get('status') == 'eligible'
                      for s, inv in ((x, a), (y, b)))
        reviewed = quality and x['id'] in groups[0] and y['id'] in groups[1]
        confirmed = reviewed and groups[0][x['id']] == groups[1][y['id']]
        if not quality:
            status, reason = 'unavailable', 'A guarded local stage interior fails quality prerequisites.'
        elif reviewed:
            status = 'reviewed association' if confirmed else 'different reviewed stages'
            reason = 'Source-bound reviewer stage-group declarations; not independently verified field identity or clock alignment.'
        elif pattern != y['phase_pattern']:
            status, reason = 'inconsistent', 'Elevated phase-current patterns differ; infeed differences also require review.'
        elif counts[0][pattern] > 1 or counts[1][pattern] > 1:
            status, reason = 'ambiguous', 'Repeated phase pattern has multiple possible stage matches; ordinal pairing is withheld.'
        elif x['kind'] != y['kind']:
            status, reason = 'ambiguous', 'Stage context differs; incomplete capture or reclose evidence needs review.'
        elif x['kind'] == 'initial candidate' and onset_association.get('status') == 'candidate':
            status, reason = 'candidate', 'Unique initial pattern and advisory onset shape agree; same-stage confirmation is still required.'
        else:
            status, reason = 'review required', 'Phase pattern alone cannot identify a physical fault stage; no stage-specific shape validation.'
        out['pairs'].append({'left_stage': x['id'], 'right_stage': y['id'],
                             'left_local_s': [x['start_s'], x['end_s']], 'right_local_s': [y['start_s'], y['end_s']],
                             'status': status, 'reason': reason, 'confirmed': confirmed,
                             'review_group': groups[0][x['id']] if confirmed else None,
                             'reviewers': [a['review']['reviewer'], b['review']['reviewer']] if reviewed else []})
    out.update(status='review required', reason='Candidates retain all alternatives; no event/stage identity or synchronization is confirmed.')
    if any(p['confirmed'] for p in out['pairs']):
        out.update(status='reviewed associations', confirmed=True,
                   reason='Selected stage identities are confirmed under reviewer declarations only; clocks and estimator windows are unchanged.')
    return out
