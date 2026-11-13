"""Bounded, read-only XLSX evidence import; formulas are never calculated.

Worksheet dimensions are untrusted. Actual XML coordinates establish the bounds
before openpyxl sees the workbook. Blank rows/cells and source row numbers remain
in the snapshot; this module never supplies missing asset identities.
"""
from __future__ import annotations

import hashlib
import io
import math
import posixpath
import re
import zipfile
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import unquote, urlsplit

SCHEMA = 'dranalyser.xlsx-snapshot.v1'
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_SHEETS = 64
MAX_ROWS = 10_000
MAX_COLUMNS = 128
MAX_CELLS = 1_000_000
MAX_PARTS = 2048
_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_COORDINATE = re.compile(r'([A-Z]{1,3})([1-9][0-9]*)\Z')


def _coordinate(raw):
    match = _COORDINATE.fullmatch(raw or '')
    if not match:
        raise ValueError('Invalid worksheet cell coordinate.')
    letters, row = match.groups()
    column = 0
    for letter in letters:
        column = column * 26 + ord(letter) - 64
    row = int(row)
    if row > MAX_ROWS or column > MAX_COLUMNS:
        raise ValueError('Worksheet exceeds the row or column limit.')
    return row, column


def _part_name(name):
    if (not name or name.startswith('/') or '\\' in name or ':' in name
            or any(ord(c) < 32 for c in name) or '%' in name
            or any(p in ('', '.', '..') for p in name.rstrip('/').split('/'))):
        raise ValueError('Unsafe XLSX ZIP part path.')
    return name


def _relationship_target(part, target):
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or '\\' in target:
        raise ValueError('External or unsafe XLSX relationship.')
    target = unquote(parsed.path)
    # A relationship lives in <source-dir>/_rels/<source-file>.rels.
    source_dir = posixpath.dirname(posixpath.dirname(part))
    resolved = posixpath.normpath(posixpath.join(source_dir, target)) if not target.startswith('/') else target[1:]
    return _part_name(resolved)


def _scan_xml(data, part, safe_xml):
    """Validate every XML part, retaining only bounded worksheet metadata."""
    result = {'sheets': [], 'relationships': {}, 'rows': 0, 'columns': 0, 'cells': 0,
              'formulas': [], 'formula_count': 0, 'worksheet': False, 'xml_parts': []}
    worksheet = False
    current_row = 0
    last_row = 0
    last_column = 0
    cell_coordinate = None
    for event, element in safe_xml.iterparse(io.BytesIO(data), events=('start', 'end'),
                                           forbid_dtd=True, forbid_entities=True, forbid_external=True):
        tag = element.tag
        if event == 'start':
            if tag == f'{{{_NS}}}worksheet':
                worksheet = True
                result['worksheet'] = True
            if worksheet and tag == f'{{{_NS}}}row':
                try:
                    current_row = int(element.get('r', last_row + 1))
                except ValueError as exc:
                    raise ValueError('Invalid worksheet row coordinate.') from exc
                if not last_row < current_row <= MAX_ROWS:
                    raise ValueError('Worksheet row coordinates must increase within the row limit.')
                last_row, last_column = current_row, 0
                result['rows'] = max(result['rows'], current_row)
            if worksheet and tag == f'{{{_NS}}}c':
                row, column = _coordinate(element.get('r'))
                if row != current_row or column <= last_column:
                    raise ValueError('Ambiguous or duplicate worksheet cell coordinate.')
                last_column = column
                result['columns'] = max(result['columns'], column)
                result['cells'] += 1
                if result['cells'] > MAX_CELLS:
                    raise ValueError('Workbook exceeds the cell limit.')
                # The coordinate is retained only while this cell is parsed.
                cell_coordinate = element.get('r')
            if worksheet and tag == f'{{{_NS}}}f':
                if cell_coordinate is None:
                    raise ValueError('Formula has no worksheet cell coordinate.')
                result['formula_count'] += 1
                if len(result['formulas']) < 100:
                    result['formulas'].append(cell_coordinate)
            continue
        if tag == f'{{{_NS}}}c':
            cell_coordinate = None
        if tag == f'{{{_NS}}}sheet':
            result['sheets'].append(dict(element.attrib))
            if len(result['sheets']) > MAX_SHEETS:
                raise ValueError('Workbook exceeds the sheet limit.')
        if tag.endswith('}Relationship'):
            kind = element.get('Type', '').lower()
            if element.get('TargetMode', '').lower() == 'external' or any(
                    bad in kind for bad in ('externallink', 'vbaproject', 'oleobject', 'macrosheet')):
                raise ValueError('Macros, embedded objects and external references are unsupported.')
            target = _relationship_target(part, element.get('Target', ''))
            identity = element.get('Id')
            if not identity or identity in result['relationships']:
                raise ValueError('Duplicate or missing XLSX relationship ID.')
            result['relationships'][identity] = target
        if tag.endswith('}Override') or tag.endswith('}Default'):
            content_type = element.get('ContentType', '').lower()
            if any(bad in content_type for bad in ('macroenabled', 'vbaproject', 'externallink', 'oleobject')):
                raise ValueError('Macros, embedded objects and external references are unsupported.')
            if content_type.endswith(('+xml', '/xml')):
                if tag.endswith('}Override'):
                    result['xml_parts'].append(_part_name(element.get('PartName', '').lstrip('/')))
                elif element.get('Extension', '').lower() not in ('xml', 'rels', 'vml'):
                    raise ValueError('Unsupported XML part extension in XLSX content types.')
        element.clear()
    return result


def _preflight(raw, safe_xml):
    metadata = {}
    total_expanded = 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_PARTS:
                raise ValueError('Workbook exceeds the ZIP part limit.')
            names = set()
            for entry in entries:
                name = _part_name(entry.filename)
                if name.casefold() in names:
                    raise ValueError('Duplicate XLSX ZIP part.')
                names.add(name.casefold())
                if entry.flag_bits & 1:
                    raise ValueError('Encrypted XLSX files are unsupported.')
                if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError('Unsupported XLSX ZIP compression.')
                if entry.file_size > MAX_MEMBER_BYTES:
                    raise ValueError('XLSX ZIP part exceeds the expanded size limit.')
                total_expanded += entry.file_size
                if total_expanded > MAX_EXPANDED_BYTES:
                    raise ValueError('Workbook exceeds the expanded size limit.')
                lower = name.lower()
                if any(bad in lower for bad in ('vbaproject', 'externallinks/', 'macrosheets/', 'embeddings/')):
                    raise ValueError('Macros, embedded objects and external references are unsupported.')
                with archive.open(entry) as stream:
                    data = stream.read(MAX_MEMBER_BYTES + 1)
                if len(data) != entry.file_size or len(data) > MAX_MEMBER_BYTES:
                    raise ValueError('Invalid or oversized XLSX ZIP part.')
                if lower.endswith(('.xml', '.rels', '.vml')):
                    metadata[name] = _scan_xml(data, name, safe_xml)
    except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError) as exc:
        raise ValueError('Invalid XLSX ZIP archive.') from exc
    try:
        sheets = metadata['xl/workbook.xml']['sheets']
        relationships = metadata['xl/_rels/workbook.xml.rels']['relationships']
        xml_parts = metadata['[Content_Types].xml']['xml_parts']
    except KeyError as exc:
        raise ValueError('Missing required XLSX workbook parts.') from exc
    if not sheets:
        raise ValueError('Workbook has no worksheets.')
    if any(part not in metadata for part in xml_parts):
        raise ValueError('Missing or unsupported XML part in XLSX content types.')
    result, titles, ids, parts = [], set(), set(), set()
    total_cells = 0
    for sheet in sheets:
        try:
            title, sid = sheet['name'], int(sheet['sheetId'])
            part = relationships[sheet[f'{{{_REL_NS}}}id']]
            bounds = metadata[part]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Invalid XLSX sheet metadata or missing worksheet.') from exc
        if (not title or sid <= 0 or title.casefold() in titles or sid in ids or part in parts
                or not bounds['worksheet']):
            raise ValueError('Duplicate or invalid XLSX sheet identity.')
        titles.add(title.casefold())
        ids.add(sid)
        parts.add(part)
        total_cells += bounds['rows'] * bounds['columns']
        if total_cells > MAX_CELLS:
            raise ValueError('Workbook exceeds the cell limit, including blank cells.')
        result.append((title, sid, bounds))
    return result


def _json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('Workbook contains a non-finite numeric value.')
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        raise ValueError('Workbook duration values require an explicit source unit.')
    raise ValueError('Workbook contains an unsupported cell value.')


def read_workbook(raw: bytes, filename: str) -> dict:
    """Return source evidence from bounded XLSX bytes without writing or executing it."""
    if (not isinstance(filename, str) or not filename.lower().endswith('.xlsx')
            or len(filename) > 255 or filename in ('.xlsx', '..xlsx')
            or any(c in filename for c in ('/', '\\', ':'))
            or any(ord(c) < 32 for c in filename)):
        raise ValueError('Supply a plain .xlsx file name.')
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_FILE_BYTES:
        raise ValueError('XLSX file must contain at most 16 MiB of bytes.')
    try:
        from defusedxml import ElementTree as safe_xml
        from defusedxml.common import DefusedXmlException
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ValueError('XLSX import requires the application dependencies openpyxl and defusedxml.') from exc
    try:
        sheets = _preflight(raw, safe_xml)
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True, keep_links=False)
        try:
            if workbook.sheetnames != [title for title, _, _ in sheets]:
                raise ValueError('Unsupported or inconsistent workbook sheet types.')
            output, warnings = [], []
            for title, sid, bounds in sheets:
                worksheet = workbook[title]
                # Ignore both inflated and understated dimension attributes.
                worksheet.reset_dimensions()
                values = []
                if bounds['rows'] and bounds['columns']:
                    for row in worksheet.iter_rows(min_row=1, max_row=bounds['rows'],
                                                   min_col=1, max_col=bounds['columns'], values_only=True):
                        values.append([_json_value(value) for value in row])
                elif bounds['rows']:
                    values = [[] for _ in range(bounds['rows'])]
                header_row = next((index for index, row in enumerate(values, 1)
                                   if ('Station Name' in row and ('Feeder Name' in row or 'PTR Name' in row))
                                   or ('Substation Name' in row and 'Transformer (PTR) Capacity' in row)), None)
                output.append({'properties': {'title': title, 'sheetId': sid}, 'values': values,
                               'row_numbers': list(range(1, len(values) + 1)), 'header_row': header_row})
                for coordinate in bounds['formulas']:
                    warnings.append({'code': 'formula_cached_value', 'sheet': title, 'cell': coordinate,
                                     'detail': 'Formula not executed; only the saved cached value is used. '
                                               'It may be missing or stale.'})
                if bounds['formula_count'] > len(bounds['formulas']):
                    warnings.append({'code': 'formula_cached_value', 'sheet': title,
                                     'count': bounds['formula_count'] - len(bounds['formulas']),
                                     'detail': 'Additional formulas were not executed; saved cached values '
                                               'may be missing or stale.'})
        finally:
            workbook.close()
    except (DefusedXmlException, safe_xml.ParseError) as exc:
        raise ValueError('Invalid or unsafe XLSX workbook.') from exc
    except ValueError:
        raise
    except (KeyError, IndexError, TypeError,
            OverflowError, zipfile.BadZipFile, OSError) as exc:
        raise ValueError('Invalid or unsafe XLSX workbook.') from exc
    return {'schema': SCHEMA,
            'source': {'kind': 'xlsx', 'file_name': filename, 'sha256': hashlib.sha256(raw).hexdigest(),
                       'retrieved_at': datetime.now(timezone.utc).isoformat()},
            'sheets': output, 'warnings': warnings}
