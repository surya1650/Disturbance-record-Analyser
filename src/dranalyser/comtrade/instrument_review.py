"""Explicit, source-bound instrument inputs applied before P/S normalization.

Original bytes and identities are never rewritten. A review is a declared input,
not independent authentication of transformer ratings or wiring.
"""
from dataclasses import replace
import hashlib
import json
import math
import re


def clean_instrument_review(raw):
    if raw is None or raw == {}:
        return {}
    fields = {'record_hash', 'reviewer', 'evidence', 'confirmed_secondary', 'ratios'}
    if not isinstance(raw, dict) or set(raw) != fields:
        raise ValueError('Supply recording hash, reviewer, rating evidence, secondary confirmation and ratios.')
    if not isinstance(raw['record_hash'], str) or not re.fullmatch('[0-9a-f]{64}', raw['record_hash']):
        raise ValueError('Instrument inputs require the exact original recording hash.')
    result = dict(record_hash=raw['record_hash'], confirmed_secondary=True)
    for key, limit in (('reviewer', 120), ('evidence', 2000)):
        value = raw[key]
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError('Supply '+key+' for the actual CT/VT ratings; defaults are not accepted.')
        result[key] = value.strip()
    if raw['confirmed_secondary'] is not True:
        raise ValueError('Confirm the recorded secondary designation and a/b gains for the actual ratings.')
    ratios = raw['ratios']
    if not isinstance(ratios, dict) or not 1 <= len(ratios) <= 64:
        raise ValueError('Supply actual ratings for the listed missing-ratio channels.')
    result['ratios'] = {}
    for key in ratios:
        if not isinstance(key, str) or not re.fullmatch('A[1-9][0-9]*', key):
            raise ValueError('Instrument ratings require original analog channel IDs.')
    for key, values in sorted(ratios.items()):
        if not isinstance(values, dict) or set(values) != {'primary', 'secondary'}:
            raise ValueError(key+': enter primary and secondary ratings.')
        if any(type(v) not in (int, float) or not 1e-9 <= v <= 1e12 or not math.isfinite(v)
               for v in values.values()):
            raise ValueError(key+': ratings must be finite positive actual values in A or V.')
        if not 1e-12 <= values['primary']/values['secondary'] <= 1e12:
            raise ValueError(key+': primary/secondary factor exceeds the supported numerical range.')
        result['ratios'][key] = dict(values)
    return result


def review_digest(review):
    return hashlib.sha256(json.dumps(review or {}, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def apply_instrument_review(cfg, raw, original_hash):
    """Clone only missing secondary rating declarations; leave samples/gains alone."""
    review = clean_instrument_review(raw)
    if not review:
        return cfg, {}
    if review['record_hash'] != original_hash:
        raise ValueError('Instrument inputs belong to a different original recording. Review them again.')
    needed = {}
    for i, channel in enumerate(cfg.analogs, 1):
        p, s = channel.primary, channel.secondary
        valid = all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in (p, s)) and p != s
        if channel.ps.strip().upper() == 'S' and channel.uu.strip().upper() in ('A', 'KA', 'V', 'KV') and not valid:
            needed['A'+str(i)] = channel
    if set(review['ratios']) - set(needed):
        raise ValueError('Instrument inputs may only name original missing secondary-ratio channels.')
    channels = []
    for i, channel in enumerate(cfg.analogs, 1):
        values = review['ratios'].get('A'+str(i))
        if values:
            unit_factor = 1000 if channel.uu.strip().upper() in ('KA', 'KV') else 1
            channel = replace(channel, primary=values['primary']/unit_factor,
                              secondary=values['secondary']/unit_factor)
        channels.append(channel)
    return replace(cfg, analogs=channels), review


def reviewed_inventory(rows, review):
    """Effective headers retain the recorded declarations alongside supplied inputs."""
    result = []
    for row in rows:
        row = dict(row)
        values = review.get('ratios', {}).get(row.get('id'))
        if values:
            unit = str(row.get('declared_units', row.get('unit', ''))).strip().upper()
            divisor = 1000 if unit in ('KA', 'KV') else 1
            row.update(recorded_primary=row.get('primary'), recorded_secondary=row.get('secondary'),
                       primary=values['primary']/divisor, secondary=values['secondary']/divisor,
                       instrument_reviewed=True)
        result.append(row)
    return result
