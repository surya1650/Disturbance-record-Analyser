"""Explicit instrument-rating review produces a traceable copy, never edits originals."""
import hashlib
import json
import math
import re
import tempfile
from pathlib import Path

import numpy as np

from ..comtrade.conformance import check
from ..comtrade.parser import read_cff, read_comtrade
from ..comtrade.source_container import _framed
from .source_inspection import _source


def required_ratios(source):
    def positive(value):
        try:
            return math.isfinite(float(value)) and float(value) > 0
        except (ValueError, TypeError):
            return False
    return [h for h in source.get('header_inventory', []) if h['kind'] == 'analog'
            and h.get('primary_secondary', '').strip().upper() == 'S'
            and h.get('declared_units', '').strip().upper() in ('A', 'KA', 'V', 'KV')
            and not (positive(h.get('primary')) and positive(h.get('secondary')))]


def prepare_ratio_copy(root, row, filename, review):
    source, item = _source(root, row, filename)
    if source.get('join') or Path(filename).suffix.lower() not in ('.cfg', '.cff'):
        raise ValueError('Review an original CFG/DAT or CFF capture, not a joined timeline.')
    if not isinstance(review, dict) or set(review)-{'record_hash', 'reviewer', 'evidence', 'confirmed_secondary', 'ratios'}:
        raise ValueError('Provide the recording hash, reviewer, evidence, secondary confirmation and channel ratios.')
    if review.get('record_hash') != item.get('content_hash') or not re.fullmatch('[0-9a-f]{64}', str(review.get('record_hash', ''))):
        raise ValueError('Ratio review belongs to a different recording. Reopen this capture.')
    for field, limit in (('reviewer', 120), ('evidence', 2000)):
        if not isinstance(review.get(field), str) or not review[field].strip() or len(review[field]) > limit:
            raise ValueError('Supply '+field+' for the actual CT/VT ratings; defaults are not accepted.')
    if review.get('confirmed_secondary') is not True:
        raise ValueError('Confirm that the CFG-declared secondary quantities and their a/b gains are appropriate for these ratings.')
    required = required_ratios(source)
    ratios = review.get('ratios')
    if not required:
        raise ValueError('This capture has no missing secondary instrument ratios to review.')
    if not isinstance(ratios, dict) or set(ratios) != {h['id'] for h in required}:
        raise ValueError('Provide primary and secondary ratings for every listed missing-ratio channel, and no other channels.')
    clean = dict(record_hash=review['record_hash'], reviewer=review['reviewer'].strip(),
                 evidence=review['evidence'].strip(), confirmed_secondary=True, ratios={})
    for h in required:
        values = ratios[h['id']]
        if not isinstance(values, dict) or set(values) != {'primary', 'secondary'}:
            raise ValueError(h['id']+': enter both primary and secondary ratings.')
        for value in values.values():
            if type(value) not in (float, int) or not math.isfinite(value) or not 1e-9 <= value <= 1e12:
                raise ValueError(h['id']+': ratings must be finite positive numbers, not zero or a guessed default.')
        factor = values['primary']/values['secondary']
        if not 1e-12 <= factor <= 1e12:
            raise ValueError(h['id']+': the primary/secondary factor exceeds the supported numerical range.')
        clean['ratios'][h['id']] = dict(values)
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
                    original_channel_inventory=source.get('header_inventory', []),
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
