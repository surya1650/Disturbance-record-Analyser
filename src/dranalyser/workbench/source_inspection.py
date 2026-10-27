"""Revision-scoped source inspection, independent of operational eligibility."""
import hashlib
import threading
from collections import OrderedDict
from pathlib import Path

from ..comtrade.source_observations import load_source

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
            if source.get('source_sha256', {}) != hashes:
                # Unsupported containers may not decode a header, but still have
                # verified original bytes and an explicit local failure status.
                if source['status'] != 'unsupported':
                    raise ValueError('Source checksum changed during decode.')
            source['source_sha256'] = hashes
            header = _header_information(cfg, cfg_hash)
            source['header_inventory'] = header.get('inventory') or item.get('channel_inventory', [])
            source['recorded_times'] = header.get('recorded_times', {})
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
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin1')
    lines = [line.strip() for line in text.replace('\x1a', '').splitlines() if line.strip()]
    try:
        counts = lines[1].split(',')
        na, nd = int(counts[1][:-1]), int(counts[2][:-1])
        if (counts[1][-1:] != 'A' or counts[2][-1:] != 'D' or not 0 <= na <= 64
                or not 0 <= nd <= 256 or int(counts[0]) != na+nd or len(lines) < 2+na+nd):
            return {}
        inventory = []
        for i, line in enumerate(lines[2:2+na+nd]):
            fields = line.split(',')
            analog = i < na
            inventory.append(dict(id=f'A{i+1}' if analog else f'D{i-na+1}',
                source_id=fields[0], kind='analog' if analog else 'digital', label=fields[1],
                phase=fields[2] if analog and len(fields)>2 else '',
                normal_state=fields[4] if not analog and len(fields)>4 else None,
                **({key: fields[pos] if len(fields)>pos else '' for key,pos in
                    [('a',5),('b',6),('primary',10),('secondary',11),('primary_secondary',12)]} if analog else {}),
                declared_units=fields[4] if analog and len(fields) > 4 else 'state' if not analog else 'Not available'))
        times=dict(start=None,trigger=None,basis='CFG recorded strings; timezone and trigger semantics are unverified.')
        try:
            j=2+na+nd
            rates=int(lines[j+1])
            index=j+2+max(rates,1)
            if 0<=rates<=8 and len(lines)>index+1:
                times.update(start=lines[index],trigger=lines[index+1])
        except (ValueError,IndexError):
            pass
        return dict(inventory=inventory,recorded_times=times)
    except (ValueError, IndexError):
        return {}


def _axis(source):
    return {k: v for k, v in source['axis'].items() if k not in ('elapsed_s', 'raw_period_runs')}


def _channels(source):
    return [dict(id=c['key'], label=c['label'], kind=kind,
                 units=c.get('units', 'state'), scaling_verified=False)
            for kind, channels in (('analog', source['channels']), ('digital', source['digital'])) for c in channels]


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
    for meta, data in zip(channels, source['channels']+source['digital'], strict=True):
        meta['trace'] = _trace(data.get('values', data.get('states', [])), times, budget)
    missing = sum(v is None for c in source['channels']+source['digital'] for v in c.get('values', c.get('states', [])))
    issues = list(source['issues'])
    if missing:
        issues.append(f'{missing} missing channel observations; gaps remain unknown.')
    status = 'partial' if missing or (issues and source['sample_count']) else source['status']
    return dict(file=filename, revision=revision['number'], status=status, issues=issues,
                sample_count=source['sample_count'], channels=channels, time_basis=_axis(source),
                source_sha256=source['source_sha256'], content_hash=source['content_hash'],
                content_hash_basis='SHA256(original CFG bytes + original DAT bytes); distinct from legacy parser hash',
                time_range_s=[times[0], times[-1]] if times else None,
                station=source.get('station', ''), device=source.get('device', ''),
                recorded_times=source.get('recorded_times', {}),
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
    return dict(file=filename, revision=revision['number'], channel_id=channel_id,
                source_sha256=source['source_sha256'], time_basis=_axis(source), units=data.get('units', 'state'),
                samples=[[i, times[i] if times else None, values[i]] for i in range(start_index, stop_index)],
                note='Zero-based source indices; nearest actual sample, no interpolation. Unknown is null.')
