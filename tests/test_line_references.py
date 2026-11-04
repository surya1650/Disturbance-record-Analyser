"""Published constants stay source-labelled and never identify an incident line."""
import json

import pytest

from dranalyser.workbench.line_references import (
    get_line_reference,
    line_reference_catalogue,
    list_line_references,
    reference_line_review,
)


def test_catalogue_requires_explicit_choice_and_preserves_manual_fallback():
    catalogue = line_reference_catalogue()
    assert catalogue['version'] == 1
    assert catalogue['selection_policy'] == 'explicit-only'
    assert catalogue['default_reference_id'] is None
    assert catalogue['manual_entry_available'] is True
    assert json.loads(json.dumps(catalogue)) == catalogue
    assert get_line_reference(None) is None
    assert get_line_reference('132') is None
    assert get_line_reference('unknown-conductor') is None


def test_panther_row_preserves_published_values_units_and_locator():
    row = get_line_reference('erpc-2015-powergrid-panther-132-sc')
    assert row['kv'] == 132
    assert row['conductor'] == 'Single Panther'
    assert row['circuit_configuration'] == 'single-circuit'
    assert row['parameters'] == {'r1': .1622, 'x1': .3861, 'r0': .4056, 'x0': 1.622}
    assert row['basis'] == 'per-km'
    assert row['units'] == 'ohm/phase/km (primary)'
    assert row['source']['printed_page'] == 36
    assert row['source']['pdf_page'] == 39
    assert row['source']['url'].startswith('https://erpc.gov.in/wp-content/uploads/2016/08/')
    assert row['source']['alternate_url'].startswith('https://www.erpc.gov.in/meetings/multiple-document/download/')
    assert row['source']['url'].endswith('#page=39')
    assert '4 November 2015' in row['source']['locator']
    assert '6 January 2016' in row['source']['edition']


def test_reference_does_not_claim_a_standard_or_known_operating_conditions():
    row = list_line_references()[0]
    assert row['reference_only'] is True
    assert row['is_standard'] is False
    assert row['requires_applicability_review'] is True
    assert row['measured_for_incident_line'] is False
    assert set(row['conditions']) == {'frequency_hz', 'conductor_temperature_c', 'tower_geometry',
                                     'earth_resistivity_ohm_m', 'transposition'}
    assert all(value is None for value in row['conditions'].values())
    assert any('different Single Panther' in note for note in row['limitations'])
    assert all(key not in row for key in ('length_km', 'confirmed_line', 'uniform_line', 'ends'))


def test_callers_cannot_mutate_catalogue_or_another_draft():
    first = list_line_references()
    selected = get_line_reference(first[0]['id'])
    first[0]['parameters']['x1'] = 999
    first[0]['source']['printed_page'] = 999
    selected['conditions']['frequency_hz'] = 50
    selected['limitations'].clear()
    pristine = list_line_references()[0]
    assert pristine['parameters']['x1'] == .3861
    assert pristine['source']['printed_page'] == 36
    assert pristine['conditions']['frequency_hz'] is None
    assert pristine['limitations']


def test_explicit_reference_draft_sets_no_incident_confirmation_or_zero_sequence():
    draft = reference_line_review('erpc-2015-powergrid-panther-132-sc')
    assert draft['r1'] == .1622 and draft['x1'] == .3861
    assert draft['basis'] == 'per-km'
    assert draft['reference_reviewed'] is False
    assert draft['reference_id'] == 'erpc-2015-powergrid-panther-132-sc'
    assert '4 November 2015' in draft['evidence']
    assert all(key not in draft for key in ('r0', 'x0', 'length_km', 'confirmed_line',
                                           'uniform_line', 'confirmed_same_event', 'ends', 'reviewer'))
    with pytest.raises(ValueError, match='unavailable'):
        reference_line_review('132')
