"""Published reference evidence stays explicit without releasing new locations."""
import copy
import json
import re
from html import unescape

import pytest
import yaml

from dranalyser.report.incident_line import line_diagram_view
from dranalyser.report.incident_summary import render_incident_report
from dranalyser.workbench.incident_inputs import prepare_incident_line
from dranalyser.workbench.incident_line import build_line_diagram
from dranalyser.workbench.line_reference_review import reference_provenance
from dranalyser.workbench.line_references import get_line_reference, reference_line_review
from dranalyser.workbench.source_snapshot import line_facts
from tests.test_incident_inputs import row_and_review
from tests.test_incident_line import declared

REFERENCE_ID = 'erpc-2015-powergrid-panther-132-sc'


def draft(reviewed=False):
    row, review = row_and_review()
    review.update(reference_line_review(REFERENCE_ID), reference_reviewed=reviewed)
    entry, assignments = prepare_incident_line(row, review)
    row['metadata'] = dict(incident_line=entry, assignments=assignments)
    return row


def frozen(tmp_path, reference=None):
    row, _ = row_and_review()
    folder = tmp_path/'runs'/row['incident_id']/str(row['number'])
    folder.mkdir(parents=True)
    data = dict(id='SYNTHETIC-LINE', name='Declared synthetic circuit', kv=132,
        terminals={end: dict(substation='Station '+end) for end in ('S', 'R')},
        sections=[dict(from_km=0, to_km=10, r1=.1622, x1=.3861, r0=None, x0=None)])
    if reference:
        data['review_provenance'] = dict(line_reference=reference)
    path = folder/'line.yaml'
    path.write_text(yaml.safe_dump(data), encoding='utf-8')
    row['result'] = dict(line_snapshot=str(path), parameter_status='unverified',
        location_text='4.000 km from Station S by E5 (conditional)')
    return row, path


@pytest.mark.parametrize('reviewed', [False, True])
def test_draft_reference_keeps_source_values_and_explicit_applicability_without_location(reviewed):
    row = draft(reviewed)
    original = copy.deepcopy(row)
    facts = line_facts('.', row)
    reference = facts['line_reference']
    expected = get_line_reference(REFERENCE_ID)
    expected.update(applicability_reviewed=reviewed, applied_parameters=['kv', 'basis', 'r1', 'x1'])
    assert reference == expected
    assert reference['conditions']['frequency_hz'] is None
    assert not reference['measured_for_incident_line'] and not reference['is_standard']
    assert facts['sections'][0]['r1_ohm_per_km'] == .1622
    assert facts['sections'][0]['r0_ohm_per_km'] is None
    assert facts['location']['km_from_S'] is None and not facts['location']['overlay_eligible']
    diagram = build_line_diagram(row, facts, [], facts['location'])
    assert diagram['line']['line_reference'] == reference
    assert diagram['fault']['status'] == 'unavailable'
    assert not line_diagram_view(diagram)['has_fault']
    assert row == original
    json.dumps(diagram, allow_nan=False)


def test_stale_draft_never_reuses_reference_evidence():
    row = draft(True)
    row['files'][0]['sha256'] = 'd'*64
    facts = line_facts('.', row)
    assert 'line_reference' not in facts
    assert facts['length_km'] is None and facts['location']['km_from_S'] is None
    assert 'stale' in facts['provenance']


def test_frozen_reference_keeps_its_complete_saved_citation_and_does_not_refresh_catalogue(tmp_path, monkeypatch):
    reference = reference_provenance(dict(reference_id=REFERENCE_ID, reference_reviewed=True))
    row, path = frozen(tmp_path, reference)
    from dranalyser.workbench import line_reference_review
    monkeypatch.setattr(line_reference_review, 'get_line_reference', lambda value: pytest.fail('Frozen reference must not be refreshed.'))
    facts = line_facts(tmp_path, row)
    assert facts['line_reference'] == reference
    assert facts['line_reference']['source']['printed_page'] == 36
    assert facts['line_reference']['parameters']['x0'] == 1.622
    assert facts['sections'][0]['x0_ohm_per_km'] is None
    assert facts['location']['km_from_S'] == 4
    original_location = copy.deepcopy(facts['location'])
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    data.pop('review_provenance')
    path.write_text(yaml.safe_dump(data), encoding='utf-8')
    manual = line_facts(tmp_path, row)
    assert 'line_reference' not in manual
    assert manual['location'] == original_location
    assert manual['sections'] == facts['sections']


@pytest.mark.parametrize('eligible', [False, True])
def test_reference_provenance_changes_neither_marker_eligibility_nor_numerical_evidence(eligible):
    row, facts, sources, location = declared()
    if not eligible:
        location['status'] = 'Not available'
    before = build_line_diagram(row, facts, sources, location)
    facts['line_reference'] = reference_provenance(dict(reference_id=REFERENCE_ID, reference_reviewed=True))
    after = build_line_diagram(row, facts, sources, location)
    assert after['fault'] == before['fault']
    assert after['terminals'] == before['terminals']
    assert after['fault']['status'] == ('eligible' if eligible else 'unavailable')
    assert after['line'].pop('line_reference') == facts['line_reference']
    assert after == before


@pytest.mark.parametrize('reviewed', [False, True, None, 'true'])
def test_primary_report_names_published_source_and_only_explicit_applicability_review(reviewed):
    row, facts, sources, location = declared()
    reference = reference_provenance(dict(reference_id=REFERENCE_ID, reference_reviewed=True))
    reference['applicability_reviewed'] = reviewed
    facts['line_reference'] = reference
    diagram = build_line_diagram(row, facts, sources, location)
    original = copy.deepcopy(diagram)
    html = render_incident_report(dict(incident_id='synthetic', revision=1, line_diagram=diagram))
    text = unescape(re.sub('<[^>]+>', ' ', html))
    assert 'Published reference impedance (positive sequence)' in text
    expected = 'applicability reviewed by user' if reviewed is True else 'applicability unreviewed'
    assert expected in text and 'not measured for this line' in text
    assert '31st ERPC minutes, item E1, printed page 36' in text
    assert 'Powergrid email of 4 November 2015, final row' in text
    assert reference['limitations'][1] not in text
    assert html.count('<section class="page"') == 4
    assert diagram == original


def test_reference_citation_is_bounded_and_escaped_without_source_markup():
    row, facts, sources, location = declared()
    facts['line_reference'] = dict(applicability_reviewed=True,
        source=dict(locator='<img src=x onerror=alert(1)>'+('long citation '*100)))
    diagram = build_line_diagram(row, facts, sources, location)
    view = line_diagram_view(diagram)
    assert len(view['provenance_note']) < 350
    html = render_incident_report(dict(incident_id='synthetic', line_diagram=diagram))
    assert '<img ' not in html and '&lt;img src=x onerror=alert(1)&gt;' in html
    assert '…' in html
    diagram['line']['line_reference']['source'] = 'unavailable'
    assert 'Source: Published source.' in line_diagram_view(diagram)['provenance_note']


def test_manual_and_missing_reference_models_keep_historical_shapes_and_layout(tmp_path):
    row, review = row_and_review()
    entry, assignments = prepare_incident_line(row, review)
    row['metadata'] = dict(incident_line=entry, assignments=assignments)
    assert 'line_reference' not in line_facts('.', row)
    frozen_row, _ = frozen(tmp_path)
    assert 'line_reference' not in line_facts(tmp_path, frozen_row)
    row, facts, sources, location = declared()
    diagram = build_line_diagram(row, facts, sources, location)
    assert 'line_reference' not in diagram['line']
    assert line_diagram_view(diagram)['provenance_note'] == 'Declared line model (unverified).'
    html = render_incident_report(dict(incident_id='synthetic', line_diagram=diagram))
    assert 'Published reference impedance' not in html
    old = render_incident_report(dict(incident_id='historical', revision=1))
    assert '<figure class="incident-line-diagram"' not in old
    assert old.count('<section class="page"') == html.count('<section class="page"') == 4
