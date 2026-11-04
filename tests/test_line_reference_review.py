"""A reference draft is neither measured line data nor permission to calculate."""
import copy

import pytest

from dranalyser.workbench.incident_inputs import (
    clean_line_review, incident_line_missing, incident_line_model, prepare_incident_line,
)
from dranalyser.workbench.line_reference_review import reference_provenance
from dranalyser.workbench.line_references import reference_line_review
from dranalyser.workbench.source_quantities import _projection
from tests.test_incident_inputs import metadata_and_bundle, row_and_review

REFERENCE = 'erpc-2015-powergrid-panther-132-sc'


def test_manual_review_shape_stays_identical_and_empty_reference_is_not_persisted():
    _, manual = row_and_review()
    old = clean_line_review(manual)
    assert clean_line_review(dict(manual, reference_id='', reference_reviewed=False)) == old
    assert not {'reference_id', 'reference_reviewed'} & old.keys()
    assert reference_provenance(old) is None


def test_reference_draft_saves_without_authorizing_model_until_applicability_review():
    row, manual = row_and_review()
    draft = dict(manual, **reference_line_review(REFERENCE))
    original = copy.deepcopy(draft)
    entry, assignments = prepare_incident_line(row, draft)
    assert draft == original
    assert entry['review']['length_km'] == manual['length_km']
    assert entry['review']['r0'] is None and entry['review']['x0'] is None
    assert any('reference applicability' in reason for reason in incident_line_missing(entry))
    with pytest.raises(ValueError, match='reference applicability'):
        incident_line_model(dict(line_id=entry['line_id'], incident_line=entry, assignments=assignments))


def test_explicitly_reviewed_reference_freezes_provenance_without_inventing_zero_sequence():
    _, metadata, bundle = metadata_and_bundle()
    review = metadata['incident_line']['review']
    review.update(reference_line_review(REFERENCE), reference_reviewed=True)
    original = copy.deepcopy(metadata)
    model = incident_line_model(metadata, bundle)
    assert model['sections'][0]['r1'] == .1622 and model['sections'][0]['x1'] == .3861
    assert model['sections'][0]['r0'] is None and model['sections'][0]['x0'] is None
    reference = model['review_provenance']['line_reference']
    assert reference['reference_only'] and not reference['measured_for_incident_line']
    assert reference['applicability_reviewed'] is True
    assert reference['applied_parameters'] == ['kv', 'basis', 'r1', 'x1']
    assert reference['source']['printed_page'] == 36
    assert all(v is None for v in reference['conditions'].values())
    reference['source']['printed_page'] = 999
    assert incident_line_model(metadata, bundle)['review_provenance']['line_reference']['source']['printed_page'] == 36
    assert metadata == original


@pytest.mark.parametrize('field,value', [
    ('reference_id', 'unknown'), ('reference_id', True), ('reference_reviewed', 'yes'),
    ('kv', 220), ('r1', .14), ('x1', .4), ('basis', 'total'),
    ('sections', [dict(from_km=0, to_km=100, r1_ohm_per_km=.1622, x1_ohm_per_km=.3861)]),
])
def test_reference_cannot_launder_edited_or_incompatible_constants(field, value):
    _, manual = row_and_review()
    draft = dict(manual, **reference_line_review(REFERENCE))
    draft[field] = value
    with pytest.raises(ValueError):
        clean_line_review(draft)


def test_confirmation_without_reference_is_rejected_and_manual_zero_sequence_remains_independent():
    with pytest.raises(ValueError, match='Choose a published reference'):
        clean_line_review({'reference_reviewed': True})
    _, manual = row_and_review()
    review = clean_line_review(dict(manual, **reference_line_review(REFERENCE), r0=.8, x0=1.9))
    assert (review['r0'], review['x0']) == (.8, 1.9)
    assert 'r0' not in reference_provenance(review)['applied_parameters']


def test_unreviewed_reference_cannot_supply_even_an_advanced_distance_projection():
    review = reference_line_review(REFERENCE)
    line = dict(length_km=100, sections=[dict(from_km=0, to_km=100, r1_ohm_per_km=.1622, x1_ohm_per_km=.3861)],
                line_reference=reference_provenance(review))
    loops = {'AB': dict(status='Conditional source quantity', impedance_ohm=[1.622, 3.861])}
    refused = _projection(loops, line, 'AB')
    assert refused['distance_km'] is None and not refused['eligible_overlay']
    assert 'applicability is unreviewed' in refused['reason']
    line['line_reference']['applicability_reviewed'] = True
    supported = _projection(loops, line, 'AB')
    assert supported['distance_km'] == pytest.approx(10)
    assert supported['status'] == 'Conditional model projection' and not supported['authorizes_location']
