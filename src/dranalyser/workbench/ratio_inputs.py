"""Source-bound instrument inputs and optional exports preserve original bytes."""
import hashlib
import json
import math
import tempfile
from pathlib import Path

import numpy as np

from ..comtrade.conformance import check
from ..comtrade.instrument_review import clean_instrument_review
from ..comtrade.parser import read_cff, read_comtrade
from ..comtrade.source_container import _framed
from .source_inspection import _source


def clean_ratio_review(raw):
    """Validate persisted source-bound inputs at the workbench service boundary."""
    return clean_instrument_review(raw)


def required_ratios(source, *, item=None, include_auxiliary=False):
    def positive(value):
        try:
            return math.isfinite(float(value)) and float(value) > 0
        except (ValueError, TypeError):
            return False
    needed = set()
    if not include_auxiliary:
        from ..comtrade.source_identity import source_meanings
        meanings = source_meanings(source)
        for row in (item or {}).get('channel_inventory', []):
            if row.get('kind') == 'analog' and row.get('selected'):
                meanings[row['id']] = row['selected']
        meanings.update(((item or {}).get('channel_mapping') or {}).get('analog', {}))
        needed = {key for key, value in meanings.items() if value in ('IA', 'IB', 'IC', 'VA', 'VB', 'VC')}
        needed.update((source.get('instrument_review') or {}).get('ratios', {}))
    return [h for h in source.get('header_inventory', []) if h['kind'] == 'analog'
            and (include_auxiliary or h['id'] in needed)
            and h.get('primary_secondary', '').strip().upper() == 'S'
            and h.get('declared_units', '').strip().upper() in ('A', 'KA', 'V', 'KV')
            and not (positive(h.get('primary')) and positive(h.get('secondary'))
                     and float(h['primary']) != float(h['secondary']))]


def prepare_ratio_update(root, row, filename, review):
    """Recheck declared inputs on the same capture, without creating source files."""
    source, item = _source(root, row, filename)
    if source.get('join') or Path(filename).suffix.lower() not in ('.cfg', '.cff'):
        raise ValueError('Review an original CFG/DAT or CFF capture, not a joined timeline.')
    clean = clean_instrument_review(review)
    if not clean or clean['record_hash'] != item.get('content_hash'):
        raise ValueError('Instrument inputs belong to a different original recording. Reopen this capture.')
    path = Path(row['bundle']['root']) / filename
    mapping = item.get('channel_mapping') or {}
    rec = (read_cff(str(path), channel_mapping=mapping, instrument_review=clean)
           if filename.lower().endswith('.cff') else
           read_comtrade(str(path), channel_mapping=mapping, instrument_review=clean))
    if any(not np.all(np.isfinite(values)) for values in rec.analog.values()):
        raise ValueError('Instrument inputs produce nonfinite primary values; source samples are not repaired.')
    check(rec)
    return dict(record=filename, reviewed_record=filename, save_mode='same-record',
                review=clean, flags=[str(flag) for flag in rec.flags], blocked=rec.blocked())


def prepare_ratio_copy(root, row, filename, review):
    source, item = _source(root, row, filename)
    if source.get('join') or Path(filename).suffix.lower() not in ('.cfg', '.cff'):
        raise ValueError('Review an original CFG/DAT or CFF capture, not a joined timeline.')
    clean = clean_instrument_review(review)
    if not clean or clean['record_hash'] != item.get('content_hash'):
        raise ValueError('Ratio review belongs to a different recording. Reopen this capture.')
    recorded = dict(source, header_inventory=source.get('recorded_header_inventory', source.get('header_inventory', [])))
    eligible = {h['id']: h for h in required_ratios(recorded, include_auxiliary=True)}
    if not eligible:
        raise ValueError('This capture has no missing secondary instrument ratios to review.')
    if set(clean['ratios']) - set(eligible):
        raise ValueError('Instrument inputs may only name original missing secondary-ratio channels.')
    required = [eligible[key] for key in clean['ratios']]
    folder = Path(row['bundle']['root'])
    inventory = {f['name']: f for f in row['files']}

    def original(name):
        raw = (folder/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != inventory[name]['sha256']:
            raise ValueError('Original source bytes changed during ratio review.')
        return raw

    raw = original(filename)
    cff = filename.lower().endswith('.cff')
    if cff:
        cfg, marker = _framed(raw)
        if marker is None:
            raise ValueError('A complete CFF DAT payload is required for a conformance recheck.')
    else:
        cfg = raw
    lines = [line.strip() for line in cfg.decode('latin1').replace('\x1a', '').splitlines() if line.strip()]
    first = lines[0].split(',')
    first[1] += ' [RATIO REVIEW]'
    lines[0] = ','.join(first)
    for h in required:
        i = int(h['id'][1:])+1
        fields = lines[i].split(',')
        unit_factor = 1000 if h['declared_units'].strip().upper() in ('KA', 'KV') else 1
        fields[4] = fields[4].strip().upper()
        fields[12] = fields[12].strip().upper()
        fields[10] = format(clean['ratios'][h['id']]['primary']/unit_factor, '.17g')
        fields[11] = format(clean['ratios'][h['id']]['secondary']/unit_factor, '.17g')
        lines[i] = ','.join(fields)
    revised = ('\r\n'.join(lines)+'\r\n').encode('latin1')
    prefix = 'reviewed-ratios-'+hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()[:16]
    payloads = {}
    if cff:
        begin = raw.find(cfg)
        revised = raw[:begin]+revised+raw[marker.start():]
        payloads['reviewed.cff'] = revised
    else:
        if not item.get('data_file'):
            raise ValueError('A matching original DAT is required for the conformance recheck.')
        payloads.update({'reviewed.cfg': revised, 'reviewed.dat': original(item['data_file'])})
    manifest = dict(original_file=filename, original_sha256=source['source_sha256'], review=clean,
                    original_channel_inventory=recorded.get('header_inventory', []),
                    input_units='Current ratings in A; voltage ratings in V. Both sides use the same unit.',
                    original_files_unchanged=True, samples_changed=False, clock_changed=False,
                    note='User-declared instrument ratings with reviewer/evidence; not independent physical authentication.')
    with tempfile.TemporaryDirectory(prefix='dr-ratio-check-') as temporary:
        temp = Path(temporary)
        for name, content in payloads.items():
            (temp/name).write_bytes(content)
        rec = read_cff(str(temp/'reviewed.cff')) if cff else read_comtrade(str(temp/'reviewed.cfg'))
        if any(not np.all(np.isfinite(v)) for v in rec.analog.values()):
            raise ValueError('The supplied ratings or source samples produce nonfinite values; ratio review cannot repair missing or invalid samples.')
        check(rec)
        flags, blocked = [str(flag) for flag in rec.flags], rec.blocked()
    manifest.update(rechecked_flags=flags, operationally_blocked=blocked)
    payloads['instrument-review.json'] = json.dumps(manifest, indent=2).encode()
    payloads['reviewed.hdr'] = b'REVIEWED COPY: instrument ratings supplied by the user. Original files and samples are unchanged. See instrument-review.json.\n'
    files = {prefix+'/'+name: content for name, content in payloads.items()}
    return dict(files=files, flags=flags, blocked=blocked, review=clean,
                reviewed_record=prefix+('/reviewed.cff' if cff else '/reviewed.cfg'))
