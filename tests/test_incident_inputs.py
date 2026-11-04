"""Incident-local line inputs preserve capture identity and refuse unknown facts."""
import copy
import json
from types import SimpleNamespace

import pytest
import yaml

from dranalyser.workbench.incident_inputs import (clean_incident_line, clean_line_review,
    freeze_incident_line, incident_line_missing, incident_line_model, prepare_incident_line,
    validate_incident_line)


def row_and_review():
    identity = 'a'*32
    files = [dict(name=end+'/event.'+ext, sha256=('b' if end == 'S' else 'c')*64)
             for end in ('S', 'R') for ext in ('cfg', 'dat')]
    row = dict(incident_id=identity, number=1, files=files, metadata={'assignments': {
        'S/event.cfg': dict(end='S', role='primary', instrument_review={'unchanged': True},
                           channel_mapping={'unchanged': True}, rx_review={'end_specific': True})}},
        bundle={'files': [dict(name=end+'/event.cfg', kind='comtrade') for end in ('S', 'R')]})
    review = dict(length_km=100, kv=220, r1=3, x1=40, basis='total',
        reviewer='Synthetic reviewer', evidence='Synthetic declared line facts',
        confirmed_line=True, uniform_line=True, confirmed_same_event=True,
        ends={end: dict(record=end+'/event.cfg', name='Station '+end,
            current_direction='bus-to-line', vt_type='CVT', vt_location='line') for end in ('S', 'R')})
    return row, review


def metadata_and_bundle():
    row, review = row_and_review()
    entry, assignments = prepare_incident_line(row, review)
    metadata = dict(line_id=entry['line_id'], incident_line=entry, assignments=assignments)
    records = [SimpleNamespace(name=end+'/event.cfg', ct_ratio=600., vt_ratio=1200.) for end in ('S', 'R')]
    return row, metadata, SimpleNamespace(records=lambda: records)


def test_complete_model_converts_explicit_total_impedance_and_never_invents_zero_sequence(tmp_path):
    row, metadata, bundle = metadata_and_bundle()
    original = copy.deepcopy((row, metadata))
    model = incident_line_model(metadata, bundle)
    assert model['sections'] == [dict(from_km=0, to_km=100, r1=.03, x1=.4, r0=None, x0=None)]
    assert model['kv'] == 220
    assert model['terminals']['S']['substation'] == 'Station S'
    assert model['terminals']['S']['ct_ratio'] == 600
    assert model['terminals']['R']['vt_ratio'] == 1200
    assert not model['model_review_required']
    path = freeze_incident_line(metadata, tmp_path, bundle)
    assert yaml.safe_load(open(path, encoding='utf-8')) == model
    assert list(tmp_path.iterdir()) == [tmp_path/'line.yaml']
    assert (row, metadata) == original


def test_partial_facts_save_as_unknown_draft_without_releasing_a_model():
    row, _ = row_and_review()
    entry, assignments = prepare_incident_line(row, {'length_km': 83, 'ends': {}})
    assert entry['review']['length_km'] == 83
    assert entry['review']['kv'] is None and entry['review']['r1'] is None
    missing = incident_line_missing(entry)
    assert any('voltage' in value for value in missing)
    assert any('R1' in value for value in missing)
    assert any('physical end' in value for value in missing)
    assert assignments['S/event.cfg']['instrument_review'] == {'unchanged': True}
    with pytest.raises(ValueError, match='Supply nominal line voltage'):
        incident_line_model(dict(line_id=entry['line_id'], incident_line=entry))


def test_updating_same_records_preserves_source_bound_ratios_and_mappings():
    row, review = row_and_review()
    original = copy.deepcopy(row)
    entry, assignments = prepare_incident_line(row, review)
    assert assignments['S/event.cfg']['instrument_review'] == row['metadata']['assignments']['S/event.cfg']['instrument_review']
    assert assignments['S/event.cfg']['channel_mapping'] == row['metadata']['assignments']['S/event.cfg']['channel_mapping']
    assert 'rx_review' not in assignments['S/event.cfg']
    assert entry['source_sha256'] == {f['name']: f['sha256'] for f in row['files']}
    assert row == original


def test_explicit_end_order_and_names_do_not_follow_dictionary_or_upload_order():
    row, review = row_and_review()
    review['ends'] = {'R': dict(review['ends']['R'], name=''), 'S': dict(review['ends']['S'], name='Edited reference')}
    entry, _ = prepare_incident_line(row, review)
    assert entry['review']['ends']['S']['name'] == 'Edited reference'
    assert entry['review']['ends']['R']['name'] == 'R'
    assert list(entry['review']['ends']) == ['S', 'R']
    review['ends']['R']['record'] = 'S/event.cfg'
    with pytest.raises(ValueError, match='both physical ends'):
        prepare_incident_line(row, review)


@pytest.mark.parametrize('change', ['files', 'incident', 'record'])
def test_stale_or_cross_incident_line_facts_are_refused(change):
    row, metadata, _ = metadata_and_bundle()
    row['metadata'] = metadata
    assert validate_incident_line(row) == metadata['incident_line']
    if change == 'files':
        row['files'][0]['sha256'] = 'd'*64
    elif change == 'incident':
        row['incident_id'] = 'e'*32
    else:
        row['metadata']['incident_line']['review']['ends']['S']['record'] = 'other.cfg'
    with pytest.raises(ValueError):
        validate_incident_line(row)


@pytest.mark.parametrize('field', ['confirmed_line', 'uniform_line', 'confirmed_same_event'])
def test_unconfirmed_physical_facts_do_not_release_default_topology(field):
    _, metadata, bundle = metadata_and_bundle()
    metadata['incident_line']['review'][field] = False
    with pytest.raises(ValueError):
        incident_line_model(metadata, bundle)


@pytest.mark.parametrize('field', ['current_direction', 'vt_type', 'vt_location'])
def test_unknown_end_facts_never_default_to_bus_direction_or_cvt(field):
    _, metadata, bundle = metadata_and_bundle()
    metadata['incident_line']['review']['ends']['S'][field] = 'unknown'
    with pytest.raises(ValueError, match='Confirm S'):
        incident_line_model(metadata, bundle)


def test_declared_reverse_polarity_is_retained_and_unknown_ratings_are_not_unity():
    _, metadata, bundle = metadata_and_bundle()
    metadata['incident_line']['review']['ends']['R']['current_direction'] = 'line-to-bus'
    assert incident_line_model(metadata, bundle)['terminals']['R']['i_polarity'] == -1
    bundle.records()[0].ct_ratio = 0
    with pytest.raises(ValueError, match='actual instrument ratings'):
        incident_line_model(metadata, bundle)


@pytest.mark.parametrize('end', ['S', 'R'])
def test_one_end_model_needs_no_other_recording_or_same_event_confirmation(end):
    row, review = row_and_review()
    review['ends'] = {end: review['ends'][end]}
    review['confirmed_same_event'] = False
    review.update(basis='per-km', r1=.03, x1=.4)
    entry, assignments = prepare_incident_line(row, review)
    assert not incident_line_missing(entry)
    record = SimpleNamespace(name=end+'/event.cfg', ct_ratio=600., vt_ratio=1200.)
    model = incident_line_model(dict(line_id=entry['line_id'], incident_line=entry, assignments=assignments),
        SimpleNamespace(records=lambda: [record]))
    assert model['sections'][0]['r1'] == .03 and model['sections'][0]['x1'] == .4
    assert model['terminals'][end]['substation'] == 'Station '+end
    unrecorded = model['terminals']['R' if end == 'S' else 'S']
    assert unrecorded['vt_type'] == unrecorded['vt_location'] == 'unknown'
    assert 'not a physical rating' in unrecorded['instrument_basis']
    assert all('zs1' not in terminal and 'zs0' not in terminal for terminal in model['terminals'].values())


@pytest.mark.parametrize('change', ['swap', 'excluded', 'additional_primary', 'unreviewed_end'])
def test_reviewed_physical_ends_cannot_be_changed_through_assignments(change):
    _, metadata, bundle = metadata_and_bundle()
    assignments = metadata['assignments']
    if change == 'swap':
        assignments['S/event.cfg']['end'], assignments['R/event.cfg']['end'] = 'R', 'S'
    elif change == 'excluded':
        assignments['S/event.cfg'].update(end='', role='excluded')
    elif change == 'additional_primary':
        assignments['other.cfg'] = dict(end='S', role='primary')
    else:
        metadata['incident_line']['review']['ends'].pop('R')
    with pytest.raises(ValueError, match='physical ends differ'):
        incident_line_model(metadata, bundle)


def test_original_record_name_whitespace_is_identity_and_display_name_is_editable():
    row, review = row_and_review()
    name = ' S/event.cfg'
    row['files'][0]['name'] = name
    row['bundle']['files'][0]['name'] = name
    review['ends']['S'].update(record=name, name='  Edited station  ')
    entry, assignments = prepare_incident_line(row, review)
    assert entry['review']['ends']['S']['record'] == name
    assert entry['review']['ends']['S']['name'] == 'Edited station'
    assert assignments[name] == dict(end='S', role='primary')


def test_mixed_sections_keep_physical_coordinates_and_never_become_uniform():
    row, review = row_and_review()
    review.update(uniform_line=False, r1=None, x1=None, basis='', sections=[
        dict(from_km=0, to_km=60, r1_ohm_per_km=.01, x1_ohm_per_km=.1),
        dict(from_km=60, to_km=100, r1_ohm_per_km=.03, x1_ohm_per_km=.6)])
    entry, assignments = prepare_incident_line(row, review)
    assert not incident_line_missing(entry)
    records = [SimpleNamespace(name=end+'/event.cfg', ct_ratio=600., vt_ratio=1200.) for end in ('S', 'R')]
    model = incident_line_model(dict(line_id=entry['line_id'], incident_line=entry, assignments=assignments),
        SimpleNamespace(records=lambda: records))
    assert len(model['sections']) == 2 and model['sections'][1]['from_km'] == 60
    assert model['section_solver_enabled'] is False
    review['sections'][1]['from_km'] = 61
    invalid, _ = prepare_incident_line(row, review)
    assert any('contiguous' in value for value in incident_line_missing(invalid))


@pytest.mark.parametrize('raw', [{'length_km': float('nan')}, {'kv': -1}, {'x1': 0},
    {'confirmed_line': 'yes'}, {'basis': 'guess'}, {'assume_ct': 600}, {'length_km': 10**400},
    {'sections': [{'r0_ohm_per_km': -1}]}, {'sections': [{'x0_ohm_per_km': 0}]},
    {'sections': [{'from_km': -1}]}, {'sections': [{'x1_ohm_per_km': float('inf')}]}])
def test_invalid_values_and_invented_fields_are_rejected(raw):
    with pytest.raises(ValueError):
        clean_line_review(raw)


def test_total_impedance_conversion_cannot_overflow_to_infinite_model():
    _, metadata, bundle = metadata_and_bundle()
    metadata['incident_line']['review']['length_km'] = 5e-324
    with pytest.raises(ValueError, match='finite ohm/km'):
        incident_line_model(metadata, bundle)


def test_section_chainage_uses_absolute_tolerance_at_large_lengths():
    row, review = row_and_review()
    review.update(length_km=1e12, sections=[dict(from_km=0, to_km=1e12-1,
        r1_ohm_per_km=.03, x1_ohm_per_km=.4)])
    entry, _ = prepare_incident_line(row, review)
    assert any('full line length' in value for value in incident_line_missing(entry))


def test_no_line_review_remains_compatible_and_canonical_values_are_finite():
    assert clean_incident_line(None) == {}
    row, review = row_and_review()
    entry, _ = prepare_incident_line(row, review)
    json.dumps(entry, allow_nan=False)
