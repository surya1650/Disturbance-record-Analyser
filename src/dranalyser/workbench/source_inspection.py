"""Revision-scoped source inspection, independent of operational eligibility."""
import hashlib
import threading
from collections import OrderedDict
from pathlib import Path

from ..comtrade.source_observations import load_source
from ..comtrade.source_header import header_information
from .source_display import digital_activity, timeline
from .source_rms import sample_rms

MAX_SAMPLES = 20000
_CACHE = OrderedDict()
_LOCK = threading.Lock()


def _file(folder, name, inventory):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Revision recording path is unavailable.')
    path = (folder/name).resolve()
    if not path.is_relative_to(folder) or not path.is_file() or name not in inventory:
        raise ValueError('Revision recording path is unavailable.')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    value = digest.hexdigest()
    if value != inventory[name]['sha256']:
        raise ValueError('Source checksum differs from the frozen revision.')
    return path, value


def _source(root, revision, filename):
    if isinstance(filename, str) and filename.startswith('@join:'):
        from .source_join import load_join
        return load_join(root, revision, filename, _source)
    allowed = (Path(root)/'runs'/revision['incident_id']/str(revision['number'])).resolve()
    bundle = revision.get('bundle') or {}
    folder = Path(bundle.get('root', '')).resolve()
    if not folder.is_relative_to(allowed):
        raise ValueError('Revision recording path is unavailable.')
    item = next((f for f in bundle.get('files', []) if f['name'] == filename and f['kind'] == 'comtrade'), None)
    if item is None:
        raise ValueError('Record is not in this revision inventory.')
    inventory = {f['name']: f for f in revision['files']}
    cfg, cfg_hash = _file(folder, filename, inventory)
    dat, hashes = None, {cfg.name: cfg_hash}
    if item.get('data_file'):
        dat, dat_hash = _file(folder, item['data_file'], inventory)
        hashes[dat.name] = dat_hash
    key = (str(cfg), str(dat), tuple(hashes.items()))
    # At most two decoded sources, with bounded strict-loader budgets. Hashes are
    # checked on every request, even a cache hit; revision bytes remain immutable.
    with _LOCK:
        if key not in _CACHE:
            # Explicit nonexistent DAT prevents implicit discovery outside inventory.
            source = load_source(cfg, dat if dat else folder/'__unpaired_dat_not_in_inventory__')
            decoded_hashes=source.get('source_sha256', {})
            if any(hashes.get(name)!=value for name,value in decoded_hashes.items()):
                raise ValueError('Source checksum changed during decode.')
            if decoded_hashes != hashes:
                # Unsupported containers may not decode a header, but still have
                # verified original bytes and an explicit local failure status.
                if source['status'] != 'unsupported':
                    raise ValueError('Source checksum changed during decode.')
            source['source_sha256'] = hashes
            header = _header_information(cfg, cfg_hash)
            source['header_inventory'] = source.get('header_inventory') or header.get('inventory') or item.get('channel_inventory', [])
            source['recorded_times'] = source.get('recorded_times') or header.get('recorded_times', {})
            _CACHE[key] = source
            while len(_CACHE) > 2:
                _CACHE.popitem(last=False)
        _CACHE.move_to_end(key)
        return _CACHE[key], item


def _header_information(path, expected_hash):
    """Recover bounded declared identities independently of DAT decode or timing."""
    if path.suffix.lower() != '.cfg' or path.stat().st_size > 1048576:
        return {}
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError('Source checksum changed during header inspection.')
    return header_information(raw)


def _axis(source):
    return {k: v for k, v in source['axis'].items() if k not in ('elapsed_s', 'raw_period_runs')}


def _channels(source):
    return [dict(id=c['key'], label=c['label'], kind=kind,
                 units=c.get('units', 'state'), scaling_verified=False)
            for kind, channels in (('analog', source['channels']), ('digital', source['digital'])) for c in channels]


def _rms(source, channel):
    # Retained only with the existing two-source, four-million-cell decode cache.
    with _LOCK:
        cache = source.setdefault('_viewer_rms', {})
        if channel['key'] not in cache:
            cache[channel['key']] = sample_rms(source, channel)
        return cache[channel['key']]


def _trace(values, times, budget):
    """Bucket extrema for display only; any missing observation breaks the path."""
    result = []
    width = max(1, (len(values)+budget-1)//budget)
    periods = [b-a for a, b in zip(times, times[1:], strict=False)] if times else []
    gap_limit = min(periods)*8 if periods else float('inf')
    breaks = {i+1 for i, period in enumerate(periods) if period > gap_limit}
    for lo in range(0, len(values), width):
        hi = min(len(values), lo+width)
        if lo in breaks:
            result.append([lo, times[lo], None])
        good = [i for i in range(lo, hi) if values[i] is not None]
        if len(good) != hi-lo or any(i in breaks for i in range(lo+1, hi)):
            # A mixed bucket is intentionally blank; zoom/native fetch recovers
            # every observation without drawing a false bridge over missing data.
            result.append([lo, times[lo] if times else None, None])
            continue
        ids = sorted({lo, hi-1, min(good, key=values.__getitem__), max(good, key=values.__getitem__)})
        result.extend([i, times[i] if times else None, values[i]] for i in ids)
    return result


def inspection_record(root, revision, filename):
    source, item = _source(root, revision, filename)
    channels = _channels(source)
    headers = {c['id']: c for c in source.get('header_inventory', [])}
    for c in channels:
        c['phase'] = headers.get(c['id'], {}).get('phase', '')
    times = source['axis'].get('elapsed_s', [])
    budget = max(1, 16000//max(1, len(channels)*4))
    remaining_intervals = 512
    for meta, data in zip(channels, source['channels']+source['digital'], strict=True):
        meta['trace'] = _trace(data.get('values', data.get('states', [])), times, budget)
        if meta['kind'] == 'analog':
            rms = _rms(source, data)
            meta.update(rms_trace=_trace(rms['values'], times, budget),
                        rms_window_s=rms['window_s'], rms_reason=rms['reason'], rms_basis=rms['basis'])
        if meta['kind'] == 'digital':
            meta['activity'] = digital_activity(data['states'], times, limit=min(32, remaining_intervals), break_indices=source.get('break_indices', []))
            remaining_intervals -= len(meta['activity']['high_intervals'])
    missing = sum(v is None for c in source['channels']+source['digital'] for v in c.get('values', c.get('states', [])))
    issues = list(source['issues'])
    if missing:
        issues.append(f'{missing} missing channel observations; gaps remain unknown.')
    status = 'partial' if missing or (issues and source['sample_count']) else source['status']
    return dict(file=filename, revision=revision['number'], status=status, issues=issues,
                sample_count=source['sample_count'], channels=channels, time_basis=_axis(source),
                source_sha256=source['source_sha256'], content_hash=source['content_hash'],
                content_hash_basis=source.get('content_hash_basis',
                    'SHA256(original CFG bytes + original DAT bytes); distinct from legacy parser hash'),
                recovery=source.get('recovery'),
                time_range_s=[times[0], times[-1]] if times else None,
                station=source.get('station', ''), device=source.get('device', ''),
                recorded_times=source.get('recorded_times', {}),
                timeline=timeline(source),
                join=source.get('join'), break_indices=source.get('break_indices', []),
                inventory=source.get('header_inventory', []),
                operational_eligibility=dict(state=revision['state'], blocked=item.get('blocked', False),
                    reason=item.get('error', '') or 'Inspection does not establish operational eligibility.'),
                authorizes_location=False, alignment_eligible=False,
                note='Display envelopes are not cursor samples. CFG scaling is unverified; no clock or location authority.')


def inspection_samples(root, revision, filename, channel_id, start_index, stop_index):
    if (type(start_index) is not int or type(stop_index) is not int or start_index < 0
            or stop_index < start_index or stop_index-start_index > MAX_SAMPLES):
        raise ValueError('Use a half-open interval of at most 20000 native samples.')
    source, _ = _source(root, revision, filename)
    if stop_index > source['sample_count']:
        raise ValueError('Interval is outside this recording.')
    data = next((c for c in source['channels']+source['digital'] if c['key'] == channel_id), None)
    if data is None:
        raise ValueError('Channel identity is unavailable in this source.')
    times = source['axis'].get('elapsed_s', [])
    values = data.get('values', data.get('states', []))
    rms = _rms(source, data) if 'values' in data else None
    return dict(file=filename, revision=revision['number'], channel_id=channel_id,
                source_sha256=source['source_sha256'], time_basis=_axis(source), units=data.get('units', 'state'),
                samples=[[i, times[i] if times else None, values[i]] for i in range(start_index, stop_index)],
                rms_samples=[[i, times[i] if times else None, rms['values'][i]] for i in range(start_index, stop_index)] if rms else [],
                source_samples=source.get('_origins', [])[start_index:stop_index],
                note='Zero-based source indices; nearest actual sample, no interpolation. Unknown is null.')


def inspection_points(root, revision, filename, channel_ids, indices):
    """One validated decode for up to eight channels and sixteen pins plus hover."""
    if (not isinstance(channel_ids,list) or not 1<=len(channel_ids)<=8
            or any(not isinstance(c,str) or not c for c in channel_ids)
            or len(set(channel_ids))!=len(channel_ids)):
        raise ValueError('Channel IDs must be a list of 1..8 unique source identities.')
    if (not isinstance(indices,list) or not 1<=len(indices)<=17
            or any(type(i) is not int or i<0 for i in indices) or len(set(indices))!=len(indices)):
        raise ValueError('Sample indices must be a list of 1..17 unique nonnegative integers.')
    source,_=_source(root,revision,filename)
    if any(i>=source['sample_count'] for i in indices):
        raise ValueError('Sample index is outside this recording.')
    available={c['key']:c for c in source['channels']+source['digital']}
    if any(c not in available for c in channel_ids):
        raise ValueError('Channel identity is unavailable in this source.')
    times=source['axis'].get('elapsed_s',[])
    channels=[]
    for identity in channel_ids:
        c=available[identity]
        values=c.get('values',c.get('states',[]))
        rms = _rms(source, c) if 'values' in c else None
        channels.append(dict(id=identity,units=c.get('units','state'),
            samples=[[i,times[i] if times else None,values[i]] for i in indices],
            rms_samples=[[i,times[i] if times else None,rms['values'][i]] for i in indices] if rms else []))
    return dict(file=filename,revision=revision['number'],indices=indices,channels=channels,
        source_samples=[source['_origins'][i] for i in indices] if source.get('_origins') else [],
        source_sha256=source['source_sha256'],time_basis=_axis(source),
        note='Exact zero-based source observations; no interpolation. Unknown is null.')
