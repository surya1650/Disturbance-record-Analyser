"""Conservative display aliases using the parser's existing canonical mapper."""
import re
import unicodedata

from .parser import detect_phase_naming, map_channel

_PHASE = r'(?:[ABCNRY]|L?[123])'
_SIMPLE = re.compile(r'[IUV]'+_PHASE+r'$', re.I)
_DERIVED = re.compile(r'\b(?:RMS|MAG|MAGNITUDE|ANGLE|PHASOR|PEAK|DC|FREQ(?:UENCY)?)\b', re.I)


def _compact(value):
    return re.sub(r'[\s_\-.:/]+', '', unicodedata.normalize('NFKC', str(value or '')).upper())


def source_meanings(source):
    """Suggest canonical waveform roles; never rename, merge or scale samples.

    Explicit reviewed choices are applied by the caller. I0/3I0 and line-line or
    derived channels cannot become phase currents just through a prefix match.
    A valid declared phase may identify an otherwise opaque waveform label.
    """
    channels = source.get('channels', [])
    headers = {c['id']: c for c in source.get('header_inventory', [])}
    labels = [unicodedata.normalize('NFKC', str(c.get('label', ''))) for c in channels]
    naming = detect_phase_naming(labels)
    simple = [_compact(label) for label in labels if _SIMPLE.fullmatch(_compact(label))]
    phases = {re.sub(r'^[IUV]', '', label) for label in simple}
    if {'R','Y'} & phases and {'A','C'} & phases:
        return {}  # Mixed phase conventions need an explicit per-channel choice.
    out = {}
    for c, label in zip(channels, labels, strict=True):
        header = headers.get(c['key'], {})
        unit = str(header.get('declared_units') or c.get('units', '')).split(' ', 1)[0]
        phase = str(header.get('phase', ''))
        compact = _compact(label)
        words = re.split(r'[\s_\-.:/]+', label.upper().strip())
        tail = _compact(words[-1]) if words else ''
        if (_DERIVED.search(re.sub(r'[_\-.:/]+', ' ', label)) or
                re.search(r'RMS|MAG|ANGLE|PHASOR|PEAK|FREQ|FUNDAMENTAL', compact) or
                compact.startswith('DC') or compact.endswith('DC')):
            continue
        if re.search(r'(?:3?[IUV][0O]|[IUV][ABCRY]{2})', compact) and not _SIMPLE.fullmatch(compact):
            continue
        if not (_SIMPLE.fullmatch(compact) or _SIMPLE.fullmatch(tail) or re.fullmatch(_PHASE, _compact(phase))):
            continue
        target = map_channel(compact if _SIMPLE.fullmatch(compact) else label, unit, phase, naming)
        if not target:
            continue
        declared = map_channel('', unit, phase, naming) if phase else None
        if declared and declared != target:
            continue
        label_kind = 'I' if compact.startswith('I') else 'V' if compact.startswith(('U', 'V')) else ''
        if label_kind and label_kind != target[0]:
            continue
        out[c['key']] = target
    return out
