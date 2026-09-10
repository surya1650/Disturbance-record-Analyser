"""Pairwise operational evidence, independent of selected analytical primaries.

No scheme conformance, causal cross-end order or breaker state is inferred.
Local edge durations remain separate when identity/stage/timing are uncertain.
"""
from __future__ import annotations

from itertools import combinations

from ..dsp.correlation import correlate_onsets
from ..dsp.detect import GROUND_TYPES, PHASE_TYPES, THREE_PHASE
from .stages import compare_stages

POINTS = ('START', 'TRIP', 'TRIP_A', 'TRIP_B', 'TRIP_C', 'TRIP_3P', 'Z1', 'Z2', 'Z3',
          'TRIP_Z2', 'TRIP_Z3', 'CARRIER_SEND', 'CARRIER_RECV', 'CB_OPEN_A', 'CB_OPEN_B',
          'CB_OPEN_C', 'ANY_POLE_DEAD', 'ALL_POLE_DEAD', 'AR_INITIATE', 'AR_CLOSE', 'AR_LOCKOUT')
OBSERVED = ('assertion observed', 'no assertion observed')


def _point(record, name):
    signal = next((s for s in record.get('signals', []) if s['signal'] == name), None)
    state = signal['state'] if signal else 'not recorded / unmapped'
    out = {'state': state, 'channels': [], 'first_edge_inception_ms': None, 'edge_count': 0}
    if not signal:
        return out
    out['channels'] = [p['channel'] for p in signal['points']]
    onset = record.get('inception_local_s')
    edges = sorted({t for p in signal['points'] for t in p['assertions_s'] if onset is not None and t >= onset})
    out['edge_count'] = len(edges)
    if state == 'assertion observed' and edges and not any(p['initially_active'] for p in signal['points']):
        out['first_edge_inception_ms'] = (edges[0]-onset)*1000
    return out


def compare_operations(records, profiles=None):
    """All declared-terminal pairs, sorted by identity rather than role/order."""
    profiles = profiles or {}
    records = sorted((r for r in records if r.get('end') in ('S', 'R')), key=lambda r: (r['end'], r['file']))
    out = []
    for left, right in combinations(records, 2):
        same = left['end'] == right['end']
        pair = {'left': left['file'], 'right': right['file'], 'left_end': left['end'], 'right_end': right['end'],
                'left_system': left.get('protection_system', 'unknown'),
                'right_system': right.get('protection_system', 'unknown'),
                'scope': 'same terminal' if same else 'cross terminal', 'points': [],
                'status': 'not evaluable', 'notes': [],
                'association': {'status': 'unavailable', 'reason': 'record unavailable', 'applied': False}}
        pair['stage_association'] = compare_stages(left, right, pair['association'])
        out.append(pair)
        if left['status'] != 'analysed' or right['status'] != 'analysed':
            pair['notes'].append('At least one record is unavailable; operation remains unknown.')
            continue
        systems = (pair['left_system'], pair['right_system'])
        if same and set(systems) != {'Main-1', 'Main-2'}:
            pair['notes'].append('Protection-system identity is unknown, repeated or other; not a confirmed Main-1/Main-2 pair.')
        compatible = (left.get('fault_type') == right.get('fault_type') and
                      left.get('fault_type') in GROUND_TYPES + PHASE_TYPES + THREE_PHASE)
        if not compatible:
            pair['association'] = {'status': 'inconsistent', 'reason': 'fault classifications differ or are unavailable', 'applied': False}
        elif left['file'] in profiles and right['file'] in profiles:
            pair['association'] = correlate_onsets(profiles[left['file']], profiles[right['file']])
        else:
            pair['association']['reason'] = 'onset profiles unavailable in this result'
        for rec in (left, right):
            repeated = any(len(p['assertions_s']) > 1 for s in rec.get('signals', [])
                           if s['signal'].startswith(('TRIP', 'START')) for p in s['points'])
            reclose = _point(rec, 'AR_CLOSE')['state'] in ('assertion observed', 'active at capture start')
            if repeated or reclose:
                pair['association'] = {'status': 'ambiguous', 'reason': 'repeated operation or reclose evidence; stages need review', 'applied': False}
        pair['stage_association'] = compare_stages(left, right, pair['association'])
        for name in POINTS:
            a, b = _point(left, name), _point(right, name)
            if not a['channels'] and not b['channels']:
                continue
            state = ('not comparable' if a['state'] not in OBSERVED or b['state'] not in OBSERVED else
                     'different observations' if a['state'] != b['state'] else 'same observation')
            # Durations are displayed side by side. Their difference is not an
            # absolute event-time difference and has no pass/fail threshold.
            delta = None
            if (same and compatible and pair['association']['status'] == 'candidate' and
                    a['first_edge_inception_ms'] is not None and b['first_edge_inception_ms'] is not None):
                delta = b['first_edge_inception_ms']-a['first_edge_inception_ms']
            pair['points'].append({'signal': name, 'left': a, 'right': b, 'comparison': state,
                                   'local_duration_difference_ms': delta})
        differences = any(p['comparison'] == 'different observations' for p in pair['points'])
        comparable = any(p['comparison'] != 'not comparable' for p in pair['points'])
        pair['status'] = ('review differences' if differences or not compatible else
                          'observations available' if comparable else 'not evaluable')
        pair['notes'].extend(['Local durations use each record\'s detected inception; no cross-record event order is established.',
                              'Clock quality is not established here; absolute timestamps are not used for pairing.',
                              'Different capture coverage, stage, settings or scheme may explain differences; no relay is selected as correct.'])
    return sorted(out, key=lambda p: p['scope'] != 'same terminal')
