"""Derived, bounded same-relay viewing timeline; immutable originals remain authoritative."""
import copy
import hashlib
import json
import threading
from collections import OrderedDict
from datetime import timedelta
from bisect import bisect_left

from .source_display import _recorded

_CACHE = OrderedDict()
_LOCK = threading.Lock()


def load_join(root, revision, filename, loader):
    if len(filename) > 8192:
        raise ValueError('Combined source selection exceeds its request budget.')
    try:
        names = json.loads(filename.removeprefix('@join:'))
    except ValueError as exc:
        raise ValueError('Joined recording selection must be valid JSON.') from exc
    if (not isinstance(names, list) or not 2 <= len(names) <= 8
            or any(not isinstance(n, str) or not n or n.startswith('@join:') for n in names)
            or len(set(names)) != len(names)):
        raise ValueError('Select 2..8 distinct original recordings, confirmed from the same relay.')
    sources = [(name, loader(root, revision, name)[0]) for name in names]
    key = tuple((name, tuple(sorted(s['source_sha256'].items()))) for name, s in sources)
    with _LOCK:
        if key not in _CACHE:
            _CACHE.clear()
            _CACHE[key] = join_sources(sources)
        return _CACHE[key], dict(blocked=True, error='Derived same-relay viewing timeline; operational study uses original captures.')


def join_sources(sources):
    first = sources[0][1]
    for _, source in sources:
        if ((source.get('station'), source.get('device')) != (first.get('station'), first.get('device'))
                or not source.get('device') or not source.get('station')):
            raise ValueError('Declared relay identities differ or are unavailable; keep the recordings separate.')
        if source.get('header_inventory') != first.get('header_inventory'):
            raise ValueError('Channel identities, ordering, units, gains or ratios differ. Explicit channel reconciliation is required before joining.')
        if [c.get('skew_us') for c in source['channels']] != [c.get('skew_us') for c in first['channels']]:
            raise ValueError('Declared analog channel skews differ; explicit timing reconciliation is required.')
        if source.get('nominal_frequency_hz') != first.get('nominal_frequency_hz'):
            raise ValueError('Declared nominal frequencies differ; keep the recordings separate.')
        if (not source['sample_count'] or source['axis'].get('status') != 'source_time_inspection'
                or not _recorded(source.get('recorded_times', {}).get('start'))):
            raise ValueError('Each capture needs usable declared source times and a recorded start time; no clock offset is guessed.')
    n = sum(s['sample_count'] for _, s in sources)
    cells = n*(2+len(first['channels'])+len(first['digital']))
    if n > 200000 or cells > 4000000:
        raise ValueError('Combined recording exceeds the 200000-sample / 4000000-cell viewing budget.')
    ordered = sorted(sources, key=lambda entry: _recorded(entry[1]['recorded_times']['start']))
    base = _recorded(ordered[0][1]['recorded_times']['start'])
    observations, summaries = [], []
    previous_end = None
    for name, source in ordered:
        start = _recorded(source['recorded_times']['start'])
        offset = (start-base).total_seconds()
        times = source['axis']['elapsed_s']
        end = offset+times[-1]
        trigger = _recorded(source['recorded_times'].get('trigger'))
        summaries.append(dict(file=name, start_s=offset, end_s=end, samples=len(times),
            trigger_s=(trigger-base).total_seconds() if trigger else None,
            original_status=source['status'], original_issues=list(source.get('issues', [])),
            recorded_times=copy.deepcopy(source.get('recorded_times', {})), recovery=source.get('recovery'),
            boundary_delta_s=offset-previous_end if previous_end is not None else None))
        previous_end = max(previous_end if previous_end is not None else end, end)
        observations.extend((offset+t, name, i) for i, t in enumerate(times))
    observations.sort()
    if any(b[0]-a[0] <= 1e-12 for a, b in zip(observations, observations[1:], strict=False)):
        raise ValueError('Captures contain duplicate or indistinguishable timestamps. Keep parallel views; no overlapping sample is silently removed.')
    lookup = dict(sources)
    times = [o[0] for o in observations]
    for summary in summaries:
        summary['start_index'] = next(i for i, (_, name, _) in enumerate(observations) if name == summary['file'])
        t = summary['trigger_s']
        summary['trigger_index'] = None
        if t is not None and times[0] <= t <= times[-1]:
            right = bisect_left(times, t)
            summary['trigger_index'] = right if not right or times[right] == t else right-1+(t-times[right-1])/(times[right]-times[right-1])
    boundaries = [i for i in range(1, n) if observations[i][1] != observations[i-1][1]]
    out = {k: copy.deepcopy(v) for k, v in first.items() if k not in ('channels', 'digital', 'axis') and not k.startswith('_')}
    for kind, value_key in (('channels', 'values'), ('digital', 'states')):
        out[kind] = [dict(c, **{value_key: [lookup[name][kind][j][value_key][i] for _, name, i in observations]})
                     for j, c in enumerate(first[kind])]
    hashes = {f'{name}:{key}': value for name, source in sources for key, value in source['source_sha256'].items()}
    out.update(sample_count=n, source_sha256=hashes,
        content_hash=hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        content_hash_basis='SHA256 of the selected original filename/checksum map; derived timeline, not an original COMTRADE hash.',
        recorded_times=copy.deepcopy(ordered[0][1]['recorded_times']),
        axis=dict(status='joined_source_time_inspection', elapsed_s=times,
            minimum_interval_s=min(b-a for a, b in zip(times, times[1:], strict=False)),
            reason='Joined declared relay-local timestamps; no cross-boundary phasor or operational authorization.'),
        issues=['Derived same-relay timeline. Every original sample is retained in timestamp order; overlaps and gaps remain explicit.']+
               [f'{name}: {issue}' for name, s in ordered for issue in s.get('issues', [])],
        break_indices=boundaries, _origins=[[name, i] for _, name, i in observations],
        join=dict(sources=summaries, clock_basis='Matching declared relay metadata; physical relay must be confirmed by the user. Recorded local clock remains unverified.',
                  originals_preserved=True, sample_policy='All samples retained, chronological ordering, no interpolation, deduplication or clock correction.'),
        authorizes_location=False, alignment_eligible=False)
    # The first chronological capture supplies the reference trigger, not a new event inception.
    out['join']['recorded_end_local'] = (base+timedelta(seconds=times[-1])).isoformat(timespec='microseconds')
    return out
