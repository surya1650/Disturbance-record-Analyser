"""Explicit, source-bound instrument inputs applied before P/S normalization.

Original bytes and identities are never rewritten. A review is a declared input,
not independent authentication of transformer ratings or wiring.
"""
from dataclasses import replace
import hashlib
import json
import math
import re


PRIMARY_BASIS = 'PRIMARY'
_PHYSICAL_UNITS = ('A', 'KA', 'V', 'KV')


def review_basis(review):
    if not review:
        return None
    return PRIMARY_BASIS if review.get('confirmed_primary') is True else 'SECONDARY'


def _channel_ids(values):
    return all(isinstance(key, str) and re.fullmatch('A[1-9][0-9]*', key) for key in values)


def clean_instrument_review(raw):
    if raw is None or raw == {}:
        return {}
    secondary_fields = {'record_hash', 'reviewer', 'evidence', 'confirmed_secondary', 'ratios'}
    primary_fields = {'record_hash', 'reviewer', 'evidence', 'basis', 'confirmed_primary', 'primary_channels'}
    primary = isinstance(raw, dict) and set(raw) in (primary_fields, primary_fields | {'ratios'})
    if not isinstance(raw, dict) or (not primary and set(raw) != secondary_fields):
        raise ValueError('Supply recording hash, reviewer, evidence and an explicit PRIMARY or secondary instrument review.')
    if not isinstance(raw['record_hash'], str) or not re.fullmatch('[0-9a-f]{64}', raw['record_hash']):
        raise ValueError('Instrument inputs require the exact original recording hash.')
    result = dict(record_hash=raw['record_hash'])
    for key, limit in (('reviewer', 120), ('evidence', 2000)):
        value = raw[key]
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError('Supply '+key+' for the measurement basis or actual CT/VT ratings; defaults are not accepted.')
        result[key] = value.strip()
    if primary:
        if raw['basis'] != PRIMARY_BASIS or raw['confirmed_primary'] is not True:
            raise ValueError('Explicitly confirm PRIMARY values after the recorded a/b gains and physical unit conversion.')
        channels = raw['primary_channels']
        if (not isinstance(channels, list) or not 1 <= len(channels) <= 64
                or not _channel_ids(channels) or len(set(channels)) != len(channels)):
            raise ValueError('PRIMARY review requires unique original analog channel IDs.')
        if 'ratios' in raw and (not isinstance(raw['ratios'], dict) or raw['ratios']):
            raise ValueError('PRIMARY review must not supply CT/VT multiplication ratios.')
        result.update(basis=PRIMARY_BASIS, confirmed_primary=True,
                      primary_channels=sorted(channels, key=lambda value: int(value[1:])), ratios={})
        return result
    if raw['confirmed_secondary'] is not True:
        raise ValueError('Confirm the recorded secondary designation and a/b gains for the actual ratings.')
    result['confirmed_secondary'] = True
    ratios = raw['ratios']
    if not isinstance(ratios, dict) or not 1 <= len(ratios) <= 64:
        raise ValueError('Supply actual ratings for the listed missing-ratio channels.')
    result['ratios'] = {}
    if not _channel_ids(ratios):
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


def _physical_gains(unit, a, b):
    try:
        return (str(unit).strip().upper() in _PHYSICAL_UNITS and a is not None and b is not None
                and math.isfinite(float(a)) and float(a) != 0 and math.isfinite(float(b)))
    except (ValueError, TypeError, OverflowError):
        return False


def primary_reviewable_channels(rows):
    """Original S physical channels eligible for an explicit basis declaration."""
    return [dict(row) for row in rows if row.get('kind') == 'analog'
            and str(row.get('primary_secondary', row.get('ps', ''))).strip().upper() == 'S'
            and _physical_gains(row.get('declared_units', row.get('unit', '')), row.get('a'), row.get('b'))]


def apply_instrument_review(cfg, raw, original_hash, *, original_inventory=None):
    """Clone reviewed metadata before normalization; retain original sample gains."""
    review = clean_instrument_review(raw)
    if not review:
        return cfg, {}
    if review['record_hash'] != original_hash:
        raise ValueError('Instrument inputs belong to a different original recording. Review them again.')
    if review_basis(review) == PRIMARY_BASIS:
        eligible = {'A'+str(i): channel for i, channel in enumerate(cfg.analogs, 1)
                    if channel.ps.strip().upper() == 'S' and _physical_gains(channel.uu, channel.a, channel.b)}
        if original_inventory is not None:
            declared = {row['id'] for row in primary_reviewable_channels(original_inventory)}
            eligible = {key: channel for key, channel in eligible.items() if key in declared}
        if set(review['primary_channels']) - set(eligible):
            raise ValueError('PRIMARY review may only name original S physical channels with finite nonzero a and finite b gains.')
        selected = set(review['primary_channels'])
        return replace(cfg, analogs=[replace(channel, ps='P') if 'A'+str(i) in selected else channel
                                     for i, channel in enumerate(cfg.analogs, 1)]), review
    needed = {}
    for i, channel in enumerate(cfg.analogs, 1):
        p, s = channel.primary, channel.secondary
        valid = all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in (p, s)) and p != s
        if channel.ps.strip().upper() == 'S' and channel.uu.strip().upper() in _PHYSICAL_UNITS and not valid:
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
    primary = set(review.get('primary_channels', []))
    for row in rows:
        row = dict(row)
        values = review.get('ratios', {}).get(row.get('id'))
        if row.get('id') in primary:
            row.update(recorded_primary=row.get('primary'), recorded_secondary=row.get('secondary'),
                       recorded_primary_secondary='S', recorded_ps='S',
                       instrument_reviewed=True, measurement_basis=PRIMARY_BASIS,
                       measurement_basis_note='User-declared PRIMARY overrides original CFG S; CT/VT multiplication is not applied; scaling unverified.')
            if 'primary_secondary' in row:
                row['primary_secondary'] = 'P'
            if 'ps' in row:
                row['ps'] = 'P'
        elif values:
            unit = str(row.get('declared_units', row.get('unit', ''))).strip().upper()
            divisor = 1000 if unit in ('KA', 'KV') else 1
            row.update(recorded_primary=row.get('primary'), recorded_secondary=row.get('secondary'),
                       primary=values['primary']/divisor, secondary=values['secondary']/divisor,
                       instrument_reviewed=True)
        result.append(row)
    return result
