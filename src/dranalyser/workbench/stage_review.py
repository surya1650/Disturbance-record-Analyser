"""Source-bound stage identities and explicit opt-in for separate stage locations."""
import hashlib
import json
import re

CONFIRMATIONS = ('same_incident', 'same_circuit', 'stage_identity')


def clean_stage_review(raw):
    if raw is None or raw == {}:
        return {}
    allowed = {'inventory_hash', 'reviewer', 'reason', 'groups', 'location_requested', *CONFIRMATIONS}
    if not isinstance(raw, dict) or set(raw)-allowed:
        raise ValueError('Invalid stage review fields.')
    digest = raw.get('inventory_hash')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Stage review requires the exact inventory hash.')
    out = {'inventory_hash': digest}
    for key, limit in (('reviewer', 200), ('reason', 1000)):
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError('Stage review requires '+key+' within the length limit.')
        out[key] = value.strip()
    for key in CONFIRMATIONS:
        value = raw.get(key, False)
        if not isinstance(value, bool):
            raise ValueError('Stage confirmations must be explicit booleans.')
        out[key] = value
    groups = raw.get('groups')
    if not isinstance(groups, dict) or not groups or len(groups) > 512:
        raise ValueError('Stage review requires a bounded stage-to-group mapping.')
    if any(not re.fullmatch(r'stage-[1-9][0-9]*', str(k)) or not isinstance(v, str) or
           not re.fullmatch('[A-Za-z0-9_-]{1,80}', v) for k, v in groups.items()):
        raise ValueError('Use stage IDs and stage-group labels with letters, digits, underscores or hyphens.')
    if len(set(groups.values())) != len(groups):
        raise ValueError('Each group may identify only one stage in a recording; keep reclose shots separate.')
    out['groups'] = dict(groups)
    if 'location_requested' in raw:
        if not isinstance(raw['location_requested'], bool):
            raise ValueError('Stage-location permission must be an explicit boolean.')
        out['location_requested'] = raw['location_requested']
    return out


def apply_stage_review(evidence, raw=None, line_id='', incident_id=''):
    stages = evidence['stages']
    snapshot = {'record_hash': evidence['record_hash'], 'end': evidence['end'],
                'protection_system': evidence['protection_system'], 'line_id': line_id, 'incident_id': incident_id,
                'channel_mapping': evidence.get('channel_mapping', {}),
                'stages': {k: v for k, v in stages.items() if k not in ('inventory_hash', 'review', 'review_status', 'reviewed_groups')}}
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    stages.update(inventory_hash=digest, review={}, review_status='not reviewed', reviewed_groups={})
    if not raw:
        return
    review = clean_stage_review(raw)
    stages['review'] = review
    if digest != review['inventory_hash']:
        stages['review_status'] = 'stale review; record, mapping, identity or stage inventory changed'
    elif not evidence['record_hash'] or stages['status'] != 'observed':
        stages['review_status'] = 'stage source or quality prerequisites unavailable'
    elif not all(review[k] for k in CONFIRMATIONS):
        stages['review_status'] = 'explicit incident, circuit and stage confirmations required'
    else:
        eligible = {s['id'] for s in stages['intervals'] if s['stable'] and s['phase_pattern'] and (
            not stages['quality_reasons'] or s.get('estimation_window', {}).get('status') == 'eligible')}
        if not set(review['groups']) <= eligible:
            stages['review_status'] = 'selected stage is unavailable, short, or has no elevated phase-current pattern'
        else:
            stages.update(review_status='valid reviewer declaration', reviewed_groups=review['groups'])
