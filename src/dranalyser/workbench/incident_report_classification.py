"""Reuse strongly bound native source classifications independently of distance."""
from .location_summary import binding_reason

_NAMES = {'AG': 'R phase to earth', 'BG': 'Y phase to earth', 'CG': 'B phase to earth',
          'AB': 'R–Y phases', 'BC': 'Y–B phases', 'CA': 'B–R phases', 'ABC': 'Three phases',
          'ABG': 'R–Y phases to earth', 'BCG': 'Y–B phases to earth',
          'CAG': 'B–R phases to earth', 'ABCG': 'Three phases to earth'}


def stored_source_classification(revision, sources, agreements, facts):
    """No new classification: stale, unmapped and unsupported sources stay unknown."""
    result = revision.get('result') or {}
    if binding_reason(result.get('location_summary'), revision, facts.get('sha256')):
        return None
    used = result.get('used') or {}
    if (not used or set(used.values()) != {source['record'] for source in sources}
            or not all(agreements) or len(agreements) != len(sources)):
        return None
    inventory = {item['name']: item for item in (revision.get('bundle') or {}).get('files', [])}
    rows = []
    for source in sources:
        record = source['record']
        matches = [row for row in result.get('relay_evidence', []) if row.get('file') == record]
        item = inventory.get(record) or {}
        end = next((end for end, value in used.items() if value == record), None)
        if (len(matches) != 1 or source.get('status') != 'available'
                or item.get('role') != 'primary' or item.get('terminal_end') != end
                or not item.get('content_hash') or matches[0].get('record_hash') != item['content_hash']):
            return None
        row = matches[0]
        if row.get('status') != 'analysed':
            return None
        fault = row.get('fault_type')
        known = isinstance(fault, str) and fault in _NAMES
        rows.append(dict(record=record, display_label=source.get('display_label') or record,
            status='stored automatic classification' if known else 'unavailable',
            code=fault if known else None, label=_NAMES[fault] if known else 'Not established',
            reason='Native waveform analysis stored for this exact source and revision.' if known else
                'The stored native analysis did not establish a supported fault type.'))
    codes = {row['code'] for row in rows if row['code']}
    complete = all(row['code'] for row in rows)
    base = dict(sources=rows, authorizes_location=False,
                provenance='Frozen source/revision/input binding and matching native record hashes; not a new detector.')
    if len(codes) > 1:
        return dict(base, status='disagreement', label='Recordings disagree', code=None,
            reason='The stored automatic analyses classify different faults. Review both recordings; no single fault loop is selected.')
    if not complete or not codes:
        return dict(base, status='partial' if codes else 'unavailable', label='Not established', code=None,
            reason='Automatic classification is incomplete in the stored source analysis. No single fault loop is selected.')
    code = next(iter(codes))
    return dict(base, status='stored source classification', label=_NAMES[code], code=code,
        reason='Automatic classification from the source-bound stored waveform analysis; fault distance remains subject to its own gates.')
