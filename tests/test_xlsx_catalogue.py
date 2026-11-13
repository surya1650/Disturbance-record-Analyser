"""Synthetic workbooks only; private operational spreadsheet rows stay local."""
import hashlib
import io
import json
import re
import warnings
import zipfile
from datetime import date, datetime, time

import pytest

from dranalyser.registry import xlsx_catalogue as xlsx

openpyxl = pytest.importorskip('openpyxl')
pytest.importorskip('defusedxml')


def workbook_bytes(sheets=None):
    book = openpyxl.Workbook()
    book.remove(book.active)
    for title, rows in (sheets or [('Example TL', [['Station Name', 'Feeder Name', 'Bus ID'],
                                                  ['Alpha', 'Beta', '000041']])]):
        sheet = book.create_sheet(title)
        for row in rows:
            sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def rewrite(raw, replacements=None, additions=None):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            value = source.read(name)
            replacement = (replacements or {}).get(name)
            if replacement is not None:
                value = replacement(value) if callable(replacement) else replacement
            target.writestr(name, value)
        for name, value in additions or []:
            target.writestr(name, value)
    return output.getvalue()


def test_preserves_blank_rows_exact_ids_types_and_source_bytes():
    rows = [[], ['Station Name', 'Feeder Name', 'Bus ID', 'Bus Number'],
            ['Alpha', 'Beta', '000041', 41111111111111111], [], ['Gamma', 'Delta', None, 0]]
    raw = workbook_bytes([('Example TL', rows)])
    before = bytes(raw)
    result = xlsx.read_workbook(raw, 'Synthetic.xlsx')
    assert raw == before
    assert result['schema'] == xlsx.SCHEMA
    assert result['source']['kind'] == 'xlsx'
    assert result['source']['file_name'] == 'Synthetic.xlsx'
    assert result['source']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert datetime.fromisoformat(result['source']['retrieved_at']).tzinfo is not None
    assert 'spreadsheet_id' not in result['source']
    sheet = result['sheets'][0]
    assert sheet['row_numbers'] == [1, 2, 3, 4, 5]
    assert sheet['header_row'] == 2
    assert sheet['values'][0] == [None] * 4
    assert sheet['values'][2][2] == '000041'
    # The Excel writer itself rounds >16-digit numbers; the reader retains the stored number.
    assert isinstance(sheet['values'][2][3], (int, float))
    assert sheet['values'][4][2:] == [None, 0]
    assert sheet['values'][3] == [None] * 4
    json.dumps(result, allow_nan=False)


def test_raw_integer_xml_is_preserved_without_float_roundtrip():
    raw = workbook_bytes([('Example TL', [['Bus ID'], [123]])])
    raw = rewrite(raw, {'xl/worksheets/sheet1.xml': lambda data: data.replace(b'<v>123</v>', b'<v>41111111111111111</v>')})
    value = xlsx.read_workbook(raw, 'ids.xlsx')['sheets'][0]['values'][1][0]
    assert value == 41111111111111111
    assert isinstance(value, int)


def test_entirely_blank_rows_retain_source_row_positions():
    raw = workbook_bytes([('Blank PTR', [[None], [None], [None]])])
    sheet = xlsx.read_workbook(raw, 'blank.xlsx')['sheets'][0]
    assert sheet['values'] == [[], [], []]
    assert sheet['row_numbers'] == [1, 2, 3]
    assert sheet['header_row'] is None


def test_multiple_tabs_heterogeneous_headers_and_iso_dates():
    sheets = []
    for index in range(13):
        sheets.extend([(f'Example {index} TL', [['Feeder Name', 'Date', 'Station Name'],
                                               ['Beta', date(2024, 4, 3), 'Alpha']]),
                       (f'Example {index} PTR', [['Bus Number', 'Station Name', 'PTR Name', 'Time'],
                                                [0, 'Alpha', 'Transformer', time(3, 4, 5)]])])
    result = xlsx.read_workbook(workbook_bytes(sheets), 'tabs.xlsx')
    assert len(result['sheets']) == 26
    assert len({sheet['properties']['sheetId'] for sheet in result['sheets']}) == 26
    assert result['sheets'][0]['values'][1][1].startswith('2024-04-03')
    assert result['sheets'][1]['values'][1][-1] == '03:04:05'
    assert all(sheet['header_row'] == 1 for sheet in result['sheets'])
    assert result['warnings'] == []


@pytest.mark.parametrize('cached,expected', [(b'', None), (b'42', 42)])
def test_formula_is_never_executed_and_cached_value_is_marked(cached, expected):
    raw = workbook_bytes([('Example TL', [['Station Name', 'Feeder Name'], ['Alpha', '=20+22']])])
    raw = rewrite(raw, {'xl/worksheets/sheet1.xml': lambda data: re.sub(
        br'<v\s*/>|<v></v>', b'<v>' + cached + b'</v>', data)})
    result = xlsx.read_workbook(raw, 'formula.xlsx')
    assert result['sheets'][0]['values'][1][1] == expected
    assert result['warnings'][0]['code'] == 'formula_cached_value'
    assert result['warnings'][0]['cell'] == 'B2'
    assert 'not executed' in result['warnings'][0]['detail']


@pytest.mark.parametrize('dimension', [b'A1:A1', b'A1:XFD1048576'])
def test_forged_dimensions_do_not_drop_data_or_expand_allocation(dimension):
    raw = workbook_bytes()
    raw = rewrite(raw, {'xl/worksheets/sheet1.xml': lambda data: re.sub(
        br'<dimension ref="[^"]*"', b'<dimension ref="' + dimension + b'"', data)})
    result = xlsx.read_workbook(raw, 'dimension.xlsx')
    assert len(result['sheets'][0]['values']) == 2
    assert len(result['sheets'][0]['values'][0]) == 3
    assert result['sheets'][0]['values'][1][2] == '000041'


@pytest.mark.parametrize('filename', ['../x.xlsx', 'x.xlsm', 'x.xls', '.xlsx', 'x.xlsx\x00',
                                      'C:\\x.xlsx', '/x.xlsx', 'x.xlsx/other', 12])
def test_rejects_unsafe_file_names(filename):
    with pytest.raises(ValueError, match='file name'):
        xlsx.read_workbook(workbook_bytes(), filename)


@pytest.mark.parametrize('raw', [b'', b'not a zip', bytearray(b'PK')])
def test_rejects_invalid_bytes(raw):
    with pytest.raises(ValueError):
        xlsx.read_workbook(raw, 'invalid.xlsx')


@pytest.mark.parametrize('name', ['../escape.xml', '/absolute.xml', 'xl/../escape.xml',
                                 'xl\\escape.xml', 'xl/%2e%2e/escape.xml'])
def test_rejects_zip_traversal(name):
    raw = rewrite(workbook_bytes(), additions=[(name, b'<root/>')])
    with pytest.raises(ValueError, match='part path'):
        xlsx.read_workbook(raw, 'unsafe.xlsx')


def test_rejects_duplicate_zip_parts():
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        raw = rewrite(workbook_bytes(), additions=[('xl/workbook.xml', b'<root/>')])
    with pytest.raises(ValueError, match='Duplicate XLSX ZIP'):
        xlsx.read_workbook(raw, 'duplicate.xlsx')


@pytest.mark.parametrize('part', ['xl/worksheets/sheet1.xml', 'xl/styles.xml',
                                 'xl/_rels/workbook.xml.rels', '[Content_Types].xml', 'custom/unknown.xml'])
def test_all_xml_parts_reject_dtd_and_entity_expansion(part):
    malicious = b'<!DOCTYPE root [<!ENTITY e "expanded">]><root>&e;</root>'
    raw = rewrite(workbook_bytes(), {part: malicious} if part != 'custom/unknown.xml' else None,
                  [(part, malicious)] if part == 'custom/unknown.xml' else None)
    with pytest.raises(ValueError, match='unsafe XLSX'):
        xlsx.read_workbook(raw, 'entity.xlsx')


def test_rejects_external_relationships_without_fetching():
    raw = rewrite(workbook_bytes(), {'xl/_rels/workbook.xml.rels': lambda data: data.replace(
        b'</Relationships>', b'<Relationship Id="external" Type="example/externalLink" '
        b'TargetMode="External" Target="https://example.invalid/private"/></Relationships>')})
    with pytest.raises(ValueError, match='external references'):
        xlsx.read_workbook(raw, 'external.xlsx')


def test_declared_xml_cannot_bypass_validation_with_binary_extension():
    raw = rewrite(workbook_bytes(), {'[Content_Types].xml': lambda data: data.replace(
        b'</Types>', b'<Override PartName="/xl/hidden.bin" ContentType="application/example+xml"/></Types>')},
        [('xl/hidden.bin', b'<!DOCTYPE root [<!ENTITY e "expanded">]><root>&e;</root>')])
    with pytest.raises(ValueError, match='XML part'):
        xlsx.read_workbook(raw, 'hidden-xml.xlsx')


def test_malformed_xml_is_explicit_value_error():
    raw = rewrite(workbook_bytes(), {'xl/styles.xml': b'<styleSheet>'})
    with pytest.raises(ValueError, match='unsafe XLSX'):
        xlsx.read_workbook(raw, 'malformed.xlsx')


@pytest.mark.parametrize('part', ['xl/vbaProject.bin', 'xl/externalLinks/externalLink1.xml',
                                 'xl/embeddings/oleObject1.bin'])
def test_rejects_active_or_external_parts_in_disguised_xlsx(part):
    raw = rewrite(workbook_bytes(), additions=[(part, b'dummy')])
    with pytest.raises(ValueError, match='unsupported'):
        xlsx.read_workbook(raw, 'active.xlsx')


@pytest.mark.parametrize('replacement', [b'<row r="10001"><c r="A10001" t="n"><v>1</v></c></row>',
                                          b'<row r="2"><c r="DY2" t="n"><v>1</v></c></row>',
                                          b'<row r="2"><c r="A2"/><c r="A2"/></row>'])
def test_actual_xml_coordinates_enforce_limits_despite_dimensions(replacement):
    raw = rewrite(workbook_bytes(), {'xl/worksheets/sheet1.xml': lambda data: re.sub(
        br'<row r="2">.*?</row>', replacement, data)})
    with pytest.raises(ValueError):
        xlsx.read_workbook(raw, 'coordinates.xlsx')


@pytest.mark.parametrize('limit,value', [('MAX_FILE_BYTES', 10), ('MAX_MEMBER_BYTES', 100),
                                      ('MAX_EXPANDED_BYTES', 100), ('MAX_PARTS', 2),
                                      ('MAX_CELLS', 5), ('MAX_SHEETS', 0)])
def test_resource_limits_fail_explicitly(monkeypatch, limit, value):
    monkeypatch.setattr(xlsx, limit, value)
    with pytest.raises(ValueError, match='limit|16 MiB'):
        xlsx.read_workbook(workbook_bytes(), 'limits.xlsx')


@pytest.mark.parametrize('value', [b'nan', b'inf', b'1e999'])
def test_nonfinite_cells_never_escape_as_invalid_json(value):
    raw = workbook_bytes([('Example TL', [['Bus ID'], [123]])])
    raw = rewrite(raw, {'xl/worksheets/sheet1.xml': lambda data: data.replace(b'<v>123</v>', b'<v>' + value + b'</v>')})
    with pytest.raises(ValueError):
        xlsx.read_workbook(raw, 'nonfinite.xlsx')


def test_sparse_rectangular_allocation_counts_blank_cells(monkeypatch):
    raw = workbook_bytes([('Example TL', [['first'], [], [None, None, 'last']])])
    monkeypatch.setattr(xlsx, 'MAX_CELLS', 8)
    with pytest.raises(ValueError, match='including blank cells'):
        xlsx.read_workbook(raw, 'sparse.xlsx')
