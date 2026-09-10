"""Validate and recheck per-record mapping declarations; never alter source files."""
import re

from ..comtrade.conformance import check
from ..comtrade.parser import read_cff, read_comtrade
from ..rules.signals import CANONICAL, map_signals
from .bundle import _instrument_facts

ANALOG_TARGETS = ('IA', 'IB', 'IC', 'IN', 'VA', 'VB', 'VC', 'VN')


def clean_mapping(raw):
    if raw is None or raw == {}:
        return {}
    if not isinstance(raw, dict) or set(raw) - {'record_hash', 'reason', 'analog', 'digital'}:
        raise ValueError('Channel mapping accepts record_hash, reason, analog and digital only.')
    digest, reason = raw.get('record_hash'), raw.get('reason')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Reviewed channel mapping requires the exact recording hash.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError('Describe the reviewed channel mapping in 1 to 1000 characters.')
    result = {'record_hash': digest, 'reason': reason.strip()}
    for kind, prefix, targets in [('analog', 'A', ANALOG_TARGETS), ('digital', 'D', CANONICAL)]:
        choices = raw.get(kind, {})
        if not isinstance(choices, dict) or len(choices) > 2000:
            raise ValueError('Invalid '+kind+' channel mapping.')
        for key, target in choices.items():
            if not isinstance(key, str) or not re.fullmatch(prefix+'[1-9][0-9]*', key) or target not in (*targets, 'ignore'):
                raise ValueError('Invalid reviewed channel identity or meaning: '+str(key))
        result[kind] = dict(choices)
    return result if result['analog'] or result['digital'] else {}


def inventory_for(rec):
    rows = [dict(v) for v in rec.notes.get('channel_inventory', [])]
    automatic = map_signals(list(rec.digital))
    for row in rows:
        if row['kind'] == 'digital':
            row['automatic'] = next((c for c in CANONICAL if row['key'] in automatic.channels(c)), '')
    return rows


def prepare_mappings(bundle, assignments):
    for f in bundle.records():
        f.channel_mapping = clean_mapping(assignments.get(f.name, {}).get('channel_mapping'))
        if not f.channel_mapping:
            continue
        if not f.ok or f.duplicate_of:
            raise ValueError(f.name+': unreadable or byte-duplicate record cannot be remapped.')
        path = bundle.root+'/'+f.name
        reader = read_cff if f.name.lower().endswith('.cff') else read_comtrade
        rec = reader(path, channel_mapping=f.channel_mapping)
        f.mapping_original_flags = list(f.flags)
        check(rec)
        f.flags, f.blocked = [str(flag) for flag in rec.flags], rec.blocked()
        f.channel_inventory = inventory_for(rec)
        f.ct_ratio, f.vt_ratio, f.kv_nominal = _instrument_facts(rec)
