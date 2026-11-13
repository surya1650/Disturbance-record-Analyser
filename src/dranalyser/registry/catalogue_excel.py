"""Local workbook inventory model, separate from legacy Google catalogue hashing."""
from collections import Counter, defaultdict
import re

from .catalogue import FIELDS, SCHEMA, _parse_row, column_name, digest, identity, number, ratio, text


def _parse_transformer(source, sheet, headers, values, row_number):
    """Transformer inventory is source evidence, never a scalar line model."""
    cells = dict(zip(headers, values, strict=False))
    mapped = {'station': 'Substation Name', 'bus_id': 'Bus ID', 'bus_number': 'Bus Number',
              'kv': 'Voltage  (kV)', 'ct_ratio': 'CT Ratio Adopted', 'reference': 'Reference'}
    raw = {key: cells.get(header) for key, header in mapped.items()}
    raw.update(feeder='', vt_ratio='', date='', relay='')
    title, sid = sheet['title'], sheet['sheetId']
    h = digest({'workbook_sha256': source['sha256'], 'sheet_id': sid, 'row': row_number,
                'headers': headers, 'values': values})
    locators = {key: f"'{title.replace(chr(39), chr(39)*2)}'!{column_name(headers.index(header)+1)}{row_number}"
                for key, header in mapped.items() if header in headers}
    out = {'id': f'{sid}:{row_number}:{h[:12]}', 'row_hash': h, 'kind': 'PTR',
           'circle': re.sub(r'\s+PTR$', '', title), 'sheet': title, 'sheet_id': sid,
           'row': row_number, 'url': None, 'cells': locators, 'raw': raw,
           'source_locator': {'file_name': source['file_name'], 'sha256': source['sha256'],
                              'sheet': title, 'row': row_number, 'cells': dict(locators)},
           **{key: text(raw.get(key)) for key in ('station', 'bus_id', 'bus_number', 'reference')},
           'feeder': '', 'relay': '', 'reference_date': None, 'kv': None, 'ct_ratio': None,
           'vt_ratio': None, 'length_km': None, 'z1': None, 'z0': None, 'zones': [],
           'transformer_capacity': text(cells.get('Transformer (PTR) Capacity')),
           'vector_group': text(cells.get('Vector Group')),
           'winding_voltage_raw': text(raw['kv']),
           'ct_available_raw': text(cells.get('CT Ratio Available')),
           'ct_adopted_raw': text(raw['ct_ratio']),
           'impedance_percent_raw': text(cells.get('% IMPEDANCE')),
           'source_values': list(values), 'source_headers': list(headers), 'issues': [],
           'status': 'Unreviewed transformer inventory', 'inventory_only': True,
           'electrical_values_parseable': False, 'field_verified': False,
           'settings_effective_date_verified': False, 'line_impedance_basis': 'not applicable'}
    for key in ('kv', 'ct_ratio'):
        try:
            out[key] = (number if key == 'kv' else ratio)(raw[key])
            if out[key] is None:
                raise ValueError('No source value supplied.')
            if key == 'kv' and out[key] <= 0:
                raise ValueError('Voltage must be positive.')
        except ValueError as exc:
            out[key] = None
            out['issues'].append({'code': 'inventory_value_review', 'field': key,
                                  'severity': 'warning', 'detail': str(exc)+' Original value retained.'})
    for key in ('station', 'bus_id', 'bus_number'):
        if not out[key]:
            out['issues'].append({'code': 'missing_id', 'field': key, 'severity': 'warning',
                                  'detail': 'Missing identity retained as unknown; not filled down.'})
    return out


def build_excel_catalogue(snapshot):
    source = snapshot.get('source', {})
    if (source.get('kind') != 'xlsx' or not re.fullmatch(r'[a-f0-9]{64}', source.get('sha256', ''))
            or not isinstance(source.get('file_name'), str)):
        raise ValueError('Invalid Excel source identity.')
    rows, skipped, seen = [], [], set()
    counts = Counter()
    for sheet in snapshot['sheets']:
        props, values = sheet['properties'], sheet['values']
        if props['sheetId'] in seen:
            raise ValueError('Duplicate sheet ID in snapshot.')
        seen.add(props['sheetId'])
        kind = 'TL' if props['title'].endswith(' TL') else 'PTR' if props['title'].endswith(' PTR') else None
        if kind is None:
            skipped.append(props['title'])
            continue
        header_row = sheet.get('header_row')
        if type(header_row) is not int or not 1 <= header_row <= len(values):
            raise ValueError('Missing recognized source header in '+props['title'])
        headers = [text(h) for h in values[header_row-1]]
        required = set(FIELDS.values()) if kind == 'TL' else {'Substation Name', 'Transformer (PTR) Capacity'}
        if not required.issubset(headers):
            raise ValueError('Missing required source headers in '+props['title'])
        semantic = set(FIELDS.values()) | {f'{prefix}{i}' for prefix in ('Z', 'T') for i in range(1, 5)}
        semantic |= {'Zone Impedance / Reach Settings (Ohms)', 'Substation Name',
                     'Transformer (PTR) Capacity', 'Voltage  (kV)', 'CT Ratio Adopted',
                     'CT Ratio Available', 'Vector Group', '% IMPEDANCE', 'Make / Serial No.'}
        semantic |= {f'{seq} {component} (Ω)' for seq in ('Quad +Seq', 'Quad Zero Seq') for component in ('R', 'X')}
        if any(count > 1 and header in semantic for header, count in Counter(headers).items()):
            raise ValueError('Duplicate mapped source headers in '+props['title']+'; no column was guessed.')
        positions = sheet.get('row_numbers', list(range(1, len(values)+1)))
        if positions != list(range(1, len(values)+1)):
            raise ValueError('Excel row positions must preserve every original row.')
        counts[kind] += 1
        for index in range(header_row, len(values)):
            if any(text(v) for v in values[index]):
                parser = _parse_row if kind == 'TL' else _parse_transformer
                rows.append(parser(source, props, headers, values[index], positions[index]))
    if not counts:
        raise ValueError('No supported TL or PTR inventory sheets found.')
    groups = defaultdict(list)
    for row in rows:
        if row['kind'] == 'TL':
            groups[(identity(row['station']), identity(row['feeder']), row['kv'])].append(row)
    for group in groups.values():
        if len(group) > 1:
            for row in group:
                row['duplicate_candidates'] = [r['id'] for r in group if r is not row]
    return {'schema': SCHEMA, 'source': source, 'snapshot_hash': digest(snapshot), 'rows': rows,
            'excluded_sheets': skipped, 'warnings': snapshot.get('warnings', []),
            'limits': 'Unreviewed source inventory. Bus identifiers do not establish circuit identity. '
                      'TL data requires source-bound engineering review before model use. PTR rows are inventory only. '
                      'No approved topology, event-effective relay settings, surveyed towers or field accuracy is established.',
            'summary': {'rows': len(rows), 'transmission_rows': sum(r['kind'] == 'TL' for r in rows),
                        'transformer_rows': sum(r['kind'] == 'PTR' for r in rows),
                        'transmission_tabs': counts['TL'], 'transformer_tabs': counts['PTR'],
                        'parseable_electrical_rows': sum(r['electrical_values_parseable'] for r in rows),
                        'missing_bus_id': sum(not r['bus_id'] for r in rows),
                        'duplicate_identity_rows': sum(bool(r.get('duplicate_candidates')) for r in rows),
                        'issues': dict(Counter(i['code'] for r in rows for i in r['issues'])),
                        'excluded_sheet_count': len(skipped), 'reader_warnings': len(snapshot.get('warnings', [])),
                        'field_verified_rows': 0}}
