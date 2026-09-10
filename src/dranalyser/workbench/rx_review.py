"""Explicit, revision-scoped declarations for display; never electrical corrections."""
import math
import re

from .channel_mapping import clean_mapping

CONFIRMATIONS = ('settings_identity', 'effective_at_event', 'phase_scaling_polarity', 'zero_sequence_voltage')


def clean_rx_review(raw):
    if raw is None or raw == {}:
        return {}
    allowed = {'record_hash', 'settings_hash', 'channel_mapping', 'reviewer', 'reason', 'ct_ratio', 'vt_ratio',
               *CONFIRMATIONS}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ValueError('Invalid R-X review fields.')
    result = {}
    for key in ('record_hash', 'settings_hash'):
        value = raw.get(key)
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('R-X review requires exact recording and settings hashes.')
        result[key] = value
    for key, limit in (('reviewer', 200), ('reason', 1000)):
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError('R-X review requires '+key+' and supporting evidence within the length limit.')
        result[key] = value.strip()
    result['channel_mapping'] = clean_mapping(raw.get('channel_mapping'))
    for key in CONFIRMATIONS:
        value = raw.get(key, False)
        if not isinstance(value, bool):
            raise ValueError('R-X confirmations must be explicit booleans.')
        result[key] = value
    for key in ('ct_ratio', 'vt_ratio'):
        value = raw.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
            raise ValueError('R-X settings CT/VT ratios must be finite and positive, or absent.')
        result[key] = value
    return result
