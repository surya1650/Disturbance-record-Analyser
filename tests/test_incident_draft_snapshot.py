import copy

from dranalyser.workbench.source_snapshot import line_facts
from tests.test_incident_inputs import row_and_review
from dranalyser.workbench.incident_inputs import prepare_incident_line


def test_saved_draft_length_and_names_are_visible_without_authorizing_location():
    row, review = row_and_review()
    entry, assignments = prepare_incident_line(row, dict(length_km=83, ends=review['ends']))
    row['metadata'] = dict(incident_line=entry, assignments=assignments)
    original = copy.deepcopy(row)
    facts = line_facts('.', row)
    assert facts['length_km'] == 83 and facts['kv'] is None
    assert facts['terminals'] == {'S': 'Station S', 'R': 'Station R'}
    assert facts['location']['km_from_S'] is None and not facts['location']['overlay_eligible']
    assert facts['sections'][0]['r1_ohm_per_km'] is None
    assert row == original


def test_saved_total_impedance_is_labelled_per_km_without_inventing_z0():
    row, review = row_and_review()
    entry, assignments = prepare_incident_line(row, review)
    row['metadata'] = dict(incident_line=entry, assignments=assignments)
    facts = line_facts('.', row)
    assert facts['sections'][0]['r1_ohm_per_km'] == .03
    assert facts['sections'][0]['x1_ohm_per_km'] == .4
    assert facts['sections'][0]['r0_ohm_per_km'] is None
    assert not facts['location']['overlay_eligible']


def test_changed_sources_do_not_reuse_saved_line_inputs_as_an_estimate():
    row, review = row_and_review()
    entry, assignments = prepare_incident_line(row, review)
    row['metadata'] = dict(incident_line=entry, assignments=assignments)
    row['files'][0]['sha256'] = 'd'*64
    facts = line_facts('.', row)
    assert facts['length_km'] is None and facts['sha256'] is None
    assert 'stale' in facts['provenance']
