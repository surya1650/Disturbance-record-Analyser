"""Synthetic workbook model contracts; no private asset rows are committed."""
import copy

import pytest

from dranalyser.registry.catalogue import build_catalogue, digest, reciprocal_candidates
from dranalyser.registry.catalogue_review import reviewed_line, source_candidate
from tests.test_source_catalogue import snapshot, review


def excel_snapshot():
    source = snapshot()
    source['schema'] = 'dranalyser.xlsx-snapshot.v1'
    source['source'] = {'kind': 'xlsx', 'sha256': 'a'*64, 'file_name': 'synthetic.xlsx'}
    sheet = source['sheets'][0]
    sheet['values'].insert(0, ['Synthetic heading'])
    sheet['values'].insert(2, [])
    sheet.update(header_row=2, row_numbers=list(range(1, len(sheet['values'])+1)))
    source['sheets'].append({'properties': {'title': 'Example PTR', 'sheetId': 124},
        'header_row': 1, 'row_numbers': [1, 2], 'values': [
            ['Substation Name', 'Transformer (PTR) Capacity', 'Bus ID', 'Bus Number',
             'Voltage  (kV)', 'CT Ratio Adopted', 'Vector Group', '% IMPEDANCE'],
            ['Alpha', '100 MVA / Tr1&2', '00123', None, '220/132', '1.000', 'YNd11', '12.5']]})
    return source


def test_excel_coordinates_leading_zero_ids_and_inventory_boundary():
    s = excel_snapshot()
    before = copy.deepcopy(s)
    cat = build_catalogue(s)
    assert s == before
    a, b, ptr = cat['rows']
    assert a['row'] == 4 and b['row'] == 5 and a['url'] is None
    assert a['cells']['station'].endswith('!A4')
    assert a['source_locator']['sha256'] == 'a'*64
    assert a['source_locator']['cells'] == a['cells']
    assert a['circle'] == 'Example' and a['kind'] == 'TL'
    assert ptr['kind'] == 'PTR' and ptr['bus_id'] == '00123' and ptr['bus_number'] == ''
    assert ptr['kv'] is None and ptr['winding_voltage_raw'] == '220/132'
    assert ptr['ct_ratio'] is None and ptr['ct_adopted_raw'] == '1.000'
    assert ptr['inventory_only'] and not ptr['electrical_values_parseable']
    assert reciprocal_candidates(cat, ptr['id']) == []
    assert cat['summary']['transmission_rows'] == 2 and cat['summary']['transformer_rows'] == 1
    assert cat['summary']['parseable_electrical_rows'] == 2
    assert len(reciprocal_candidates(cat, a['id'])) == 1


def test_workbook_hash_and_original_row_bind_row_identity():
    s = excel_snapshot()
    first = build_catalogue(s)['rows'][0]
    s['source']['sha256'] = 'b'*64
    second = build_catalogue(s)['rows'][0]
    assert first['id'] != second['id']
    s['sheets'][0]['row_numbers'][3] = 100
    with pytest.raises(ValueError, match='positions'):
        build_catalogue(s)


@pytest.mark.parametrize('value,expected', [('2026-11-13', '2026-11-13'),
    ('2026-11-13T00:00:00', '2026-11-13'), ('13/11/2026', '2026-11-13')])
def test_excel_reference_dates_are_not_effective_settings_dates(value, expected):
    s = excel_snapshot()
    s['sheets'][0]['values'][3][4] = value
    row = build_catalogue(s)['rows'][0]
    assert row['reference_date'] == expected
    assert not row['settings_effective_date_verified']


def test_transformers_cannot_be_promoted_even_with_forged_parseable_flag():
    cat = build_catalogue(excel_snapshot())
    ptr = cat['rows'][-1]
    ptr['electrical_values_parseable'] = True
    r = review(cat)
    r['terminals']['R'] = ptr['id']
    r['catalogue_hash'] = digest(cat)
    with pytest.raises(ValueError, match='Transformer'):
        reviewed_line(cat, r)
    s = {'catalogue_hash': digest(cat), 'line_id': 'SYNTHETIC',
         'identity_confirmation': 'Synthetic only', 'basis_interpretation': 'Explicit test',
         'impedance_basis': 'primary_total_ohm', 'terminals': r['terminals']}
    with pytest.raises(ValueError, match='Transformer'):
        source_candidate(cat, s)


def test_google_legacy_catalogue_remains_identical():
    cat = build_catalogue(snapshot())
    assert 'kind' not in cat['rows'][0]
    assert cat['rows'][0]['url'].startswith('https://docs.google.com/')
    assert cat['summary']['transmission_tabs'] == 1
    assert cat['rows'][0]['row_hash'] == digest({'spreadsheet_id': 'SYNTHETIC-ONLY',
        'sheet_id': 123, 'row': 2, 'headers': snapshot()['sheets'][0]['values'][0],
        'values': snapshot()['sheets'][0]['values'][1]})


@pytest.mark.parametrize('sheet_index,header', [(0, 'Line Length (KM)'), (0, 'T1'), (1, 'Bus ID')])
def test_duplicate_semantic_headers_cannot_misattribute_values_to_cells(sheet_index, header):
    s = excel_snapshot()
    sh = s['sheets'][sheet_index]
    sh['values'][sh['header_row']-1].append(header)
    for values in sh['values'][sh['header_row']:]:
        values.append('999')
    with pytest.raises(ValueError, match='Duplicate mapped source headers'):
        build_catalogue(s)


def test_zone_times_follow_named_columns_and_retain_exact_cell_provenance():
    s = excel_snapshot()
    sh = s['sheets'][0]
    start = sh['values'][1].index('Z1')+1
    sh['values'][1].insert(start, 'Unrelated source column')
    sh['values'][3].insert(start, 1234)
    sh['values'][4].insert(start, 5678)
    cat = build_catalogue(s)
    row = cat['rows'][0]
    assert row['zones'][0]['time_raw'] == 0
    assert row['zones'][1]['reach_raw'] == 10
    assert row['cells']['T1'].endswith('!P4')
    assert row['source_locator']['cells']['T1'] == row['cells']['T1']
    # Missing named timing is unknown, not an unrelated adjacent value.
    sh['values'][1][sh['values'][1].index('T1')] = 'Missing time label'
    assert build_catalogue(s)['rows'][0]['zones'][0]['time_raw'] is None
