"""Read-only staging of spreadsheet evidence, never an approved electrical registry.

No missing identity is filled down, no relay zone shape is inferred from a reach
vector, and neither a bus ID nor row order establishes circuit/terminal identity.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime

SCHEMA = 'dranalyser.source-catalogue.v1'
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
MISSING = {'', 'NIL', 'NA', 'N/A', '-', 'NONE'}
FIELDS = {'station': 'Station Name', 'feeder': 'Feeder Name', 'bus_id': 'Bus ID',
          'bus_number': 'Bus Number', 'date': 'Date', 'reference': 'Reference',
          'kv': 'Voltage (kV)', 'length_km': 'Line Length (KM)',
          'z1': '+Ve Seq Imp (Ω)', 'z0': 'Zero Seq Imp (Ω)',
          'ct_ratio': 'CT Ratio (Adopted)', 'vt_ratio': 'PT Ratio',
          'relay': 'Distance Relay Make & Type'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def number(value):
    raw = text(value)
    if raw.upper() in MISSING:
        return None
    if isinstance(value, bool) or not re.fullmatch(NUMBER, raw):
        raise ValueError('Expected one finite decimal number; no value was guessed.')
    result = float(raw)
    if not math.isfinite(result):
        raise ValueError('Non-finite number.')
    return result


def impedance(value):
    raw = text(value).replace('−', '-').replace(' ', '')
    if raw.upper() in MISSING:
        return None
    match = re.fullmatch(rf'({NUMBER})([+-])[jJ]({NUMBER})(?:=({NUMBER}))?', raw)
    if not match:
        raise ValueError('Expected R +j X [= magnitude] in the source; no derived-column fallback.')
    r, sign, x, magnitude = match.groups()
    result = {'r': float(r), 'x': (1 if sign == '+' else -1)*float(x),
              'stated_magnitude': float(magnitude) if magnitude is not None else None}
    if not all(v is None or math.isfinite(v) for v in result.values()):
        raise ValueError('Non-finite impedance component or magnitude.')
    return result


def ratio(value):
    raw = text(value)
    if raw.upper() in MISSING:
        return None
    match = re.fullmatch(rf'\s*({NUMBER})\s*/\s*({NUMBER})\s*[AVav]?\s*', raw)
    if not match:
        raise ValueError('Expected explicit primary / secondary ratio; no assumed secondary base.')
    primary, secondary = map(float, match.groups())
    if not all(math.isfinite(v) and v > 0 for v in (primary, secondary)):
        raise ValueError('Instrument ratio must have finite positive primary and secondary values.')
    return {'primary': primary, 'secondary': secondary, 'ratio': primary/secondary}


def column_name(index):
    result = ''
    while index:
        index, digit = divmod(index-1, 26)
        result = chr(65+digit)+result
    return result


def _parse_row(source, sheet, headers, values, row_number):
    title, sid = sheet['title'], sheet['sheetId']
    cells = {key: values[i] if i < len(values) else None for i, key in enumerate(headers)}
    raw = {key: cells.get(header) for key, header in FIELDS.items()}
    row_hash = digest({'spreadsheet_id': source['spreadsheet_id'], 'sheet_id': sid,
                       'row': row_number, 'headers': headers, 'values': values})
    out = {'id': f'{sid}:{row_number}:{row_hash[:12]}', 'row_hash': row_hash,
           'sheet': title, 'sheet_id': sid, 'row': row_number,
           'url': f"https://docs.google.com/spreadsheets/d/{source['spreadsheet_id']}/edit#gid={sid}&range=A{row_number}",
           'raw': raw, 'cells': {key: f"'{title.replace(chr(39), chr(39)*2)}'!{column_name(headers.index(h)+1)}{row_number}"
                                for key, h in FIELDS.items() if h in headers},
           'station': text(raw['station']), 'feeder': text(raw['feeder']),
           'bus_id': text(raw['bus_id']), 'bus_number': text(raw['bus_number']),
           'relay': text(raw['relay']), 'reference': text(raw['reference']),
           'reference_date': None, 'issues': [], 'status': 'unreviewed source evidence',
           'field_verified': False, 'settings_effective_date_verified': False,
           'line_impedance_basis': 'unconfirmed', 'source_values': list(values)}

    def issue(code, field, detail, severity='error'):
        out['issues'].append({'code': code, 'field': field, 'severity': severity, 'detail': detail})

    for key, parser in [('kv', number), ('length_km', number), ('z1', impedance), ('z0', impedance),
                        ('ct_ratio', ratio), ('vt_ratio', ratio)]:
        try:
            out[key] = parser(raw[key])
            if out[key] is None:
                issue('missing', key, 'No source value supplied.')
        except ValueError as exc:
            out[key] = None
            issue('invalid', key, str(exc))
    for key in ('station', 'feeder'):
        if not out[key]:
            issue('missing', key, 'No identity supplied; blank cells are not filled down.')
    for key in ('bus_id', 'bus_number'):
        if not out[key]:
            issue('missing_id', key, 'Missing identifier retained as unknown.', 'warning')
    for key in ('kv', 'length_km'):
        if out[key] is not None and out[key] <= 0:
            issue('nonpositive', key, 'Must be positive.')
    for key, prefix in [('z1', 'Quad +Seq'), ('z0', 'Quad Zero Seq')]:
        z = out[key]
        if not z:
            continue
        if not all(math.isfinite(z[k]) for k in ('r', 'x')) or z['r'] < 0 or z['x'] <= 0:
            issue('invalid_impedance', key, 'Passive scalar line requires finite R >= 0 and X > 0.')
        mag = math.hypot(z['r'], z['x'])
        if z['stated_magnitude'] is not None and abs(mag-z['stated_magnitude']) > max(.03, mag*.005):
            issue('magnitude_mismatch', key, 'Stated magnitude conflicts with source R/X.', 'warning')
        for component, label in [('r', 'R'), ('x', 'X')]:
            try:
                alternate = number(cells.get(f'{prefix} {label} (Ω)'))
                if alternate is not None and abs(alternate-z[component]) > .015:
                    issue('derived_column_conflict', key, f'{prefix} {label} conflicts with original R/X.')
            except ValueError:
                issue('invalid_derived_column', key, f'{prefix} {label} is not a finite decimal.', 'warning')
    if text(raw['date']):
        try:
            out['reference_date'] = datetime.strptime(text(raw['date']), '%d/%m/%y').date().isoformat()
        except ValueError:
            issue('unparsed_date', 'date', 'Reference date retained verbatim; not an effective settings date.', 'warning')
    # These are source reach/time values, not zone polygons or confirmed relay bases.
    start = next((i for i, h in enumerate(headers) if h in ('Z1', 'Zone Impedance / Reach Settings (Ohms)')), None)
    out['zones'] = [{'name': f'Z{i+1}', 'reach_raw': values[start+2*i] if start is not None and start+2*i < len(values) else None,
                     'time_raw': values[start+2*i+1] if start is not None and start+2*i+1 < len(values) else None,
                     'impedance_basis': 'unconfirmed', 'characteristic_complete': False} for i in range(4)]
    out['electrical_values_parseable'] = not any(i['severity'] == 'error' for i in out['issues'])
    return out


def build_catalogue(snapshot):
    if snapshot.get('schema') != 'dranalyser.google-sheet-snapshot.v1':
        raise ValueError('Unsupported snapshot schema.')
    source = snapshot['source']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', source.get('spreadsheet_id', '')):
        raise ValueError('Invalid spreadsheet ID.')
    rows, skipped = [], []
    seen_sheets = set()
    for sheet in snapshot['sheets']:
        props, values = sheet['properties'], sheet['values']
        if props['sheetId'] in seen_sheets:
            raise ValueError('Duplicate sheet ID in snapshot.')
        seen_sheets.add(props['sheetId'])
        if not props['title'].endswith(' TL'):
            skipped.append(props['title'])
            continue
        if not values or not set(FIELDS.values()).issubset(values[0]):
            raise ValueError('Missing required source headers in '+props['title'])
        for index, value in enumerate(values[1:], 2):
            if any(text(v) for v in value):
                rows.append(_parse_row(source, props, values[0], value, index))
    catalogue = {'schema': SCHEMA, 'source': source, 'snapshot_hash': digest(snapshot),
                 'rows': rows, 'excluded_sheets': snapshot.get('excluded_sheets', [])+skipped,
                 'limits': 'Unreviewed source evidence. No approved topology, surveyed towers, event-effective '
                           'relay settings, field accuracy or patrol truth is established.'}
    keys = defaultdict(list)
    for row in rows:
        keys[(identity(row['station']), identity(row['feeder']), row['kv'])].append(row)
    for group in keys.values():
        if len(group) > 1:
            for row in group:
                row['duplicate_candidates'] = [r['id'] for r in group if r is not row]
    catalogue['summary'] = {'rows': len(rows), 'transmission_tabs': len(seen_sheets)-len(skipped),
        'parseable_electrical_rows': sum(r['electrical_values_parseable'] for r in rows),
        'missing_bus_id': sum(not r['bus_id'] for r in rows),
        'duplicate_identity_rows': sum(bool(r.get('duplicate_candidates')) for r in rows),
        'issues': dict(Counter(i['code'] for r in rows for i in r['issues'])),
        'field_verified_rows': 0}
    return catalogue


def identity(value):
    """Formatting equivalence only: preserve all tokens and circuit suffixes."""
    return re.sub(r'\W+', '', text(value).upper())


def feeder_identity(value):
    # A bare trailing separator is formatting; circuit 1, 2 and 1&2 stay distinct.
    return identity(text(value).rstrip(' -'))


def reciprocal_candidates(catalogue, row_id):
    row = next((r for r in catalogue['rows'] if r['id'] == row_id), None)
    if row is None:
        raise ValueError('Unknown catalogue row.')
    station, feeder = identity(row['station']), feeder_identity(row['feeder'])
    if not station or not feeder or not row['kv']:
        return []
    candidates = []
    for other in catalogue['rows']:
        if other['id'] == row_id or other['kv'] != row['kv']:
            continue
        if identity(other['station']) == feeder and feeder_identity(other['feeder']) == station:
            disagreements = []
            for key in ('length_km', 'z1', 'z0'):
                if row[key] != other[key]:
                    disagreements.append(key)
            candidates.append({'id': other['id'], 'url': other['url'],
                'station': other['station'], 'feeder': other['feeder'], 'disagreements': disagreements,
                'status': 'candidate only; explicit circuit/end and parameter review required'})
    return candidates
