"""Declared same-recorder capture chronology; sources and gaps stay independent.

Matching recorder labels are only a candidate relation. Local CFG strings and
original DAT offsets neither verify clock accuracy nor establish a common clock.
This adapter reuses retained digital/stage observations; it detects no new event.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import math

from .incident_report_time import recorded_clock
from ..rules.signals import CANONICAL, map_signals

_DAT_BASIS = 'DAT source timestamps as declared; not calibrated time or continuous-acquisition proof'
_GROUPS = {'Trip': lambda name: name.startswith('TRIP') or name.endswith('_TRIP'),
           'AR': lambda name: name.startswith('AR_'),
           'CB position feedback': lambda name: name.startswith('CB_OPEN') or name.endswith('POLE_DEAD')}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _local_value(iso):
    """Decimal local seconds retain CFG nanoseconds without any timezone guess."""
    if not isinstance(iso, str):
        return None
    try:
        stamp = datetime.fromisoformat(iso[:19])
        fraction = Decimal('0'+iso[19:]) if len(iso) > 19 else Decimal(0)
        return Decimal(stamp.toordinal()*86400+stamp.hour*3600+stamp.minute*60+stamp.second)+fraction
    except (ValueError, InvalidOperation, OverflowError):
        return None


def _local_iso(value):
    try:
        value = value.quantize(Decimal('0.000000001'))
        whole = int(value)
        day, seconds = divmod(whole, 86400)
        stamp = datetime.fromordinal(day)+timedelta(seconds=seconds)
        fraction = format(value-whole, '.9f').rstrip('0').rstrip('.')
        return stamp.isoformat()+(fraction[1:] if fraction else '')
    except (ValueError, OverflowError):
        return None


def capture_time(source):
    """Only explicit original DAT offsets may anchor the actual capture span."""
    axis = source.get('axis') or {}
    origin = axis.get('declared_origin') or {}
    clock = recorded_clock(source.get('recorded_times'))
    out = dict(status='unavailable', cfg_start_local_iso=clock['start_local_iso'],
        first_local_iso=None, last_local_iso=None, first_offset_s=None, last_offset_s=None,
        reason='The original DAT offset from CFG start is not established; actual capture gap/overlap is unknown.',
        alignment_eligible=False, clock_accuracy_verified=False)
    first, last = origin.get('first_offset_s'), origin.get('last_offset_s')
    times = axis.get('elapsed_s') or []
    valid = (axis.get('status') == 'source_time_inspection' and axis.get('basis') == _DAT_BASIS
        and origin.get('status') == 'available' and origin.get('basis') == 'Original DAT timestamps × declared time multiplier'
        and _finite(first) and _finite(last)
        and 0 <= first <= last and len(times) == source.get('sample_count') and len(times) >= 3
        and all(_finite(t) for t in times) and times[0] == 0
        and all(b > a for a, b in zip(times, times[1:], strict=False)))
    start = _local_value(clock['start_local_iso'])
    if start is None:
        out['reason'] = 'A parseable recorder-local CFG start is unavailable; capture chronology is unknown.'
        return out
    if not valid:
        return out
    # The origin marker comes from the same valid DAT array, not a fitted rate.
    a, b = (_local_iso(start+Decimal(str(value))) for value in (first, last))
    if a is None or b is None:
        return out
    out.update(status='declared local span', first_local_iso=a, last_local_iso=b,
        first_offset_s=first, last_offset_s=last,
        reason='CFG start plus original DAT first/last declared offsets; source-local clock accuracy remains unverified.')
    return out


def signal_inventory(source, mappings):
    """Reuse supported meaning assignments, including constant digital channels."""
    rows = []
    for channel in source.get('digital', [])[:256]:
        key, label = channel['key'], channel['label']
        choice = mappings.get(key)
        suggested = map_signals([label])
        meanings = ([choice] if choice != 'ignore' else []) if choice else [
            name for name in CANONICAL if label in suggested.channels(name)]
        rows.append(dict(id=key, label=label, meanings=meanings))
    names = {name for row in rows for name in row['meanings']}
    missing = [label for label, matches in _GROUPS.items() if not any(matches(name) for name in names)]
    return dict(channels=rows, missing=missing,
        missing_note=('No assigned '+', '.join(missing)+' channels.' if missing else ''),
        basis='Existing supported label suggestions and explicit display mappings; absence of an assigned channel is not proof of no operation.')


def _stored_stages(revision, source, agree):
    inventory = {item['name']: item for item in (revision.get('bundle') or {}).get('files', [])}
    item = inventory.get(source['record']) or {}
    rows = [row for row in (revision.get('result') or {}).get('relay_evidence', [])
            if row.get('file') == source['record']]
    if (not agree or len(rows) != 1 or rows[0].get('status') != 'analysed'
            or not item.get('content_hash') or rows[0].get('record_hash') != item['content_hash']):
        return dict(status='unavailable', intervals=[], reason='No matching stored source-stage observation is available.')
    stages = rows[0].get('stages') or {}
    if (stages.get('record_hash') != item['content_hash'] or stages.get('status') != 'observed'
            or (source.get('instrument_review') or {}) != (rows[0].get('instrument_review') or {})):
        return dict(status='unavailable', intervals=[], reason='Stored stage source binding is unavailable.')
    fields = ('id', 'kind', 'phase_pattern', 'stable', 'start_s', 'end_s', 'start_boundary_range_s',
              'end_boundary_range_s', 'onset_unknown', 'continues_at_capture_end')
    intervals = [{key: copy.deepcopy(row[key]) for key in fields if key in row}
                 for row in stages.get('intervals', [])[:16] if isinstance(row, dict)]
    return dict(status=stages.get('status') or 'unavailable', intervals=intervals,
        omitted_intervals=max(0, len(stages.get('intervals', []))-len(intervals)),
        method=stages.get('method'), reason=stages.get('reason'),
        note='Stored local phase-current observations only; no new detector or physical operation is inferred.')


def build_capture_sequence(sources, revision=None, agreements=()):
    """Describe at most two independent report captures in declared local order."""
    chosen = sources[:2]
    rows = []
    for index, source in enumerate(chosen):
        timing = source.get('capture_time') or {}
        rows.append(dict(record=source['record'], display_label=source.get('display_label') or source['record'],
            station=source.get('station') or '', device=source.get('device') or '',
            cfg_start_local_iso=timing.get('cfg_start_local_iso'),
            first_local_iso=timing.get('first_local_iso'), last_local_iso=timing.get('last_local_iso'),
            span_status=timing.get('status') or 'unavailable', span_reason=timing.get('reason') or '',
            signals=copy.deepcopy((source.get('digital') or {}).get('sequence_signals') or {}),
            stages=_stored_stages(revision or {}, source, index < len(agreements) and agreements[index])))
    out = dict(version=1, status='unavailable', captures=rows, capture_limit=2,
        omitted_captures=max(0, len(sources)-2), chronology='unknown', relation=dict(status='unknown', seconds=None),
        note='', authorizes_location=False, alignment_eligible=False, clock_accuracy_verified=False,
        identity_note='Matching station/device strings are candidate evidence, not verified physical recorder identity.',
        gap_note='No state, transition, trip, reclose or breaker operation is inferred between captures. Original recordings remain independent.')
    if len(rows) != 2:
        out['reason'] = 'Two representative independent captures are required for a sequence overview.'
        return out
    identity = [tuple(str(row[key]).strip() for key in ('station', 'device')) for row in rows]
    if not all(all(value) for value in identity):
        out['reason'] = 'Nonempty station and device declarations are required for a candidate same-recorder sequence.'
        return out
    if identity[0] != identity[1]:
        out.update(status='different declared recorders', reason='Station/device declarations differ; no same-recorder sequence is established.')
        return out
    out.update(status='candidate same-recorder sequence',
        reason='Both captures declare the same station and device; physical identity and incident membership need review.')
    starts = [_local_value(row['cfg_start_local_iso']) for row in rows]
    if all(value is not None for value in starts):
        anchored = all(row['span_status'] == 'declared local span' for row in rows)
        rows.sort(key=lambda row: (_local_value(row['first_local_iso'] if anchored else row['cfg_start_local_iso']), row['record']))
        out['chronology'] = 'declared local capture start order' if anchored else 'declared CFG-local start order'
    for index, row in enumerate(rows, 1):
        row['order'] = index
    if out['chronology'] != 'unknown' and all(row['span_status'] == 'declared local span' for row in rows):
        delta = _local_value(rows[1]['first_local_iso'])-_local_value(rows[0]['last_local_iso'])
        status = 'gap' if delta > 0 else 'overlap' if delta < 0 else 'touching declared endpoints'
        out['relation'] = dict(status=status, seconds=float(abs(delta)), signed_seconds=float(delta))
        number = format(abs(delta), 'f')
        relation = (number.rstrip('0').rstrip('.') if '.' in number else number)+' s '+status
    else:
        relation = 'Capture gap/overlap unknown: original DAT origin or CFG start unavailable'
    out['note'] = 'Candidate same-recorder sequence: matching station/device declarations, identity unverified. '+relation+'. States between captures are unknown; trip–reclose–retrip is unconfirmed.'
    return out


def same_recorder_attachments(root, revision, primaries, inventory):
    """Fill one remaining display slot only with a recoverable declared peer."""
    # Keep an accepted operational result's default display cohort intact.
    # Explicit two-capture requests retain the existing source/cohort gates.
    summary = (revision.get('result') or {}).get('location_summary') or {}
    if len(primaries) != 1 or summary.get('accepted') is True:
        return []
    from . import event_study
    primary = next((item for item in inventory if item['name'] == primaries[0]), {})
    def identity(item):
        return tuple(str(item.get(key) or '').strip() for key in ('station', 'device_id'))
    declared = identity(primary)
    if not all(declared):
        return []
    for item in inventory:
        if item['name'] in primaries or identity(item) != declared or item.get('duplicate_of'):
            continue
        source, _ = event_study._source(root, revision, item['name'])
        if source.get('axis', {}).get('elapsed_s'):
            return [item['name']]
    return []
