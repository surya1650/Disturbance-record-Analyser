"""Source-bound reviewer stage grouping, including stale and partial reviews."""
import copy

import pytest

from dranalyser.application.intake import metadata_value
from dranalyser.rules.stages import compare_stages
from dranalyser.workbench.stage_review import apply_stage_review, clean_stage_review
from tests.test_stages import clean_pair


def review_for(row):
    apply_stage_review(row)
    active = [s for s in row['stages']['intervals'] if s['stable'] and s['phase_pattern']]
    return {'inventory_hash': row['stages']['inventory_hash'], 'reviewer': 'Synthetic fixture reviewer',
            'reason': 'Known independent waveform schedule; synthetic declarations only',
            'groups': {s['id']: f'physical-stage-{i}' for i, s in enumerate(active)},
            'same_incident': True, 'same_circuit': True, 'stage_identity': True}


def test_review_can_resolve_repeated_patterns_without_sync_or_window_authorization():
    rows = clean_pair()
    for row in rows:
        apply_stage_review(row, review_for(row))
    pair = compare_stages(*rows, {'status': 'ambiguous'})
    assert pair['status'] == 'reviewed associations' and pair['confirmed']
    assert len([p for p in pair['pairs'] if p['confirmed']]) == 3
    assert len([p for p in pair['pairs'] if p['status'] == 'different reviewed stages']) == 6
    assert all(p['reviewers'] == ['Synthetic fixture reviewer']*2 for p in pair['pairs'])
    assert not pair['applied']
    assert all(not r['clock_quality']['alignment_eligible'] for r in rows)


@pytest.mark.parametrize('change', ['record', 'mapping', 'bounds', 'terminal', 'system', 'line', 'policy', 'incident'])
def test_changes_invalidate_prior_review(change):
    row = clean_pair()[0]
    review = review_for(row)
    if change == 'record':
        row['record_hash'] = 'c'*64
    elif change == 'mapping':
        row['channel_mapping'] = {'reason': 'corrected mapping'}
    elif change == 'bounds':
        row['stages']['intervals'][0]['start_s'] += .01
    elif change == 'terminal':
        row['end'] = 'R'
    elif change == 'system':
        row['protection_system'] = 'other'
    elif change == 'policy':
        row['stages']['policy']['minimum_run_cycles'] = 3
    apply_stage_review(row, review, 'new-line' if change == 'line' else '', 'new-incident' if change == 'incident' else '')
    assert row['stages']['review_status'].startswith('stale')
    assert not row['stages']['reviewed_groups']
    assert row['stages']['review'] == review


@pytest.mark.parametrize('missing', ['same_incident', 'same_circuit', 'stage_identity'])
def test_confirmation_cannot_be_inferred(missing):
    row = clean_pair()[0]
    review = review_for(row)
    review[missing] = False
    apply_stage_review(row, review)
    assert not row['stages']['reviewed_groups']


def test_withdrawing_review_and_partial_review_keep_unreviewed_pairs_ambiguous():
    rows = clean_pair()
    reviews = [review_for(r) for r in rows]
    for row, review in zip(rows, reviews, strict=True):
        first = next(iter(review['groups']))
        review['groups'] = {first: 'initial'}
        apply_stage_review(row, review)
    pair = compare_stages(*rows, {'status': 'ambiguous'})
    assert sum(p['confirmed'] for p in pair['pairs']) == 1
    apply_stage_review(rows[1])
    assert not compare_stages(*rows, {'status': 'ambiguous'})['confirmed']


@pytest.mark.parametrize('bad', ['reviewer', 'reason', 'hash', 'duplicate', 'unknown', 'boolean', 'extra', 'empty'])
def test_malformed_review_is_rejected_at_shared_intake(bad):
    review = review_for(clean_pair()[0])
    if bad in ('reviewer', 'reason'):
        review[bad] = ''
    elif bad == 'hash':
        review['inventory_hash'] = 'not-a-hash'
    elif bad == 'duplicate':
        review['groups'] = {'stage-1': 'initial', 'stage-2': 'initial'}
    elif bad == 'unknown':
        review['groups'] = {'bad-id': 'initial'}
    elif bad == 'boolean':
        review['stage_identity'] = 'true'
    elif bad == 'empty':
        review['groups'] = {}
    else:
        review['clock_good'] = True
    with pytest.raises(ValueError):
        metadata_value({'assignments': {'record.cfg': {'end': 'S', 'role': 'primary', 'stage_review': review}}})


def test_unknown_interval_and_quality_cannot_be_overridden_by_a_review():
    row = clean_pair()[0]
    review = review_for(row)
    review['groups'] = {'stage-999': 'initial'}
    apply_stage_review(row, review)
    assert not row['stages']['reviewed_groups']
    row['stages']['quality_reasons'] = ['clipping']
    for stage in row['stages']['intervals']:
        stage['estimation_window']['status'] = 'withheld'
    review = review_for(row)
    apply_stage_review(row, review)
    assert not row['stages']['reviewed_groups']
    before = copy.deepcopy(review)
    assert clean_stage_review(review) == before and review == before
