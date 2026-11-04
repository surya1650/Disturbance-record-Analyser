"""Automatic source projections stay inside detected, supported fault evidence."""
import copy
import hashlib
import math

import pytest

from dranalyser.workbench.source_diagnostics import diagnose_source
from dranalyser.workbench.source_projection_window import select_projection_window
from tests.test_source_inputs import analytic_revision


def source():
    return dict(sample_count=513, axis={'elapsed_s': [i/1024 for i in range(513)]},
                channels=[], digital=[], break_indices=[])


def projected(index, support, distance=10, *, status='Conditional model projection', reason=''):
    return dict(index=index, support_s=support, projection=dict(status=status, reason=reason,
        distance_km=distance, eligible_overlay=status == 'Conditional model projection',
        authorizes_location=False, method='Public conditional model',
        basis='Declared phase loop and line model; physical facts remain unverified.'))


def region(monkeypatch, bounds=(128, 385), reason='Public bounded event'):
    from dranalyser.workbench import source_regions
    detected = dict(status='selected' if bounds else 'unavailable', fault=list(bounds) if bounds else None,
                    method='Public observed change', reason=reason, authorizes_location=False)
    calls = []

    def detect(record, item, **choices):
        calls.append((record, item, choices))
        return copy.deepcopy(detected)

    monkeypatch.setattr(source_regions, 'auto_regions', detect)
    return calls


def choose(record, rows, **options):
    return select_projection_window(record, {}, dict(mappings={}, fault_loop='AB', **options), rows)


def test_automatic_choice_uses_complete_contained_support_nearest_fault_centre(monkeypatch):
    record = source()
    calls = region(monkeypatch)
    # Large and capture-first values must not steer the interval selection.
    rows = [projected(0, [0., .125], 999), projected(1, [.125, .25], 5),
            projected(2, [.1875, .3125], 7), projected(3, [.25, .375], 8),
            projected(4, [.3125, .4375], 1000)]
    before = copy.deepcopy(rows)
    result = choose(record, rows)
    assert result['window_index'] == 2
    assert result['support_s'] == [.1875, .3125]
    assert result['distance_km'] == 7
    selection = result['window_selection']
    assert selection['mode'] == 'automatic' and selection['status'] == 'selected'
    assert selection['fault_support_s'] == [.125, .375]
    assert selection['fault_sample_indices'] == [128, 385]
    assert selection['candidate_count'] == 3
    assert not selection['authorizes_location'] and not result['authorizes_location']
    assert len(calls) == 1 and rows == before


def test_equal_centre_distance_is_resolved_by_existing_window_index(monkeypatch):
    region(monkeypatch)
    result = choose(source(), [projected(8, [.25, .375]), projected(3, [.125, .25])])
    assert result['window_index'] == 3


def test_outside_line_projection_is_retained_when_its_window_is_the_selected_support(monkeypatch):
    region(monkeypatch)
    outside = projected(2, [.1875, .3125], -12, status='Outside supplied line',
                        reason='Projection lies outside the supplied line; it is not clipped.')
    result = choose(source(), [projected(1, [.125, .25], 10), outside])
    assert result['window_index'] == 2
    assert result['status'] == 'Outside supplied line' and result['distance_km'] == -12
    assert 'outside' in result['reason'].lower()
    assert not result['eligible_overlay'] and not result['authorizes_location']


def test_no_event_has_no_whole_capture_fallback(monkeypatch):
    region(monkeypatch, None, 'No sustained change with usable baseline.')
    result = choose(source(), [projected(0, [0., .08], 10)])
    assert result['status'] == 'Not available' and result['distance_km'] is None
    assert result['window_selection']['mode'] == 'automatic'
    assert result['window_selection']['status'] == 'unavailable'
    assert 'No sustained change' in result['reason']
    assert result.get('window_index') is None


def test_short_fault_support_is_not_extended_to_fit_existing_window(monkeypatch):
    region(monkeypatch, (128, 185))
    result = choose(source(), [projected(1, [.125, .205]), projected(2, [.16, .24])])
    assert result['status'] == 'Not available' and result['distance_km'] is None
    assert result['window_selection']['candidate_count'] == 0
    assert result['window_selection']['fault_support_s'] == [.125, .1796875]
    assert 'window' in result['reason'].lower()


def test_projection_refusal_is_preserved_instead_of_selecting_an_ineligible_fit(monkeypatch):
    region(monkeypatch)
    refused = projected(2, [.1875, .3125], None, status='Not available',
                        reason='Selected loop is unavailable: a supported source fit is required.')
    result = choose(source(), [refused])
    assert result['status'] == 'Not available' and result['distance_km'] is None
    assert 'supported source fit' in result['reason']
    assert result['window_selection']['candidate_count'] == 0


def test_source_break_inside_support_cannot_be_crossed(monkeypatch):
    region(monkeypatch)
    record = source()
    record['break_indices'] = [256]
    result = choose(record, [projected(2, [.1875, .3125])])
    assert result['status'] == 'Not available' and result['distance_km'] is None
    assert result['window_selection']['candidate_count'] == 0


@pytest.mark.parametrize('location', ['source', 'axis'])
def test_declared_break_bracket_is_not_eligible_even_when_support_starts_between_samples(monkeypatch, location):
    region(monkeypatch)
    record = source()
    target = record if location == 'source' else record['axis']
    target['break_indices'] = [256]
    # The support begins in the missing bracket, so its first included native
    # sample alone cannot establish coverage across the declared break.
    result = choose(record, [projected(2, [.2495, .3125])])
    assert result['status'] == 'Not available' and result['distance_km'] is None
    assert 'break' in result['reason'].lower()


def test_automatic_choice_can_use_support_starting_after_a_declared_break(monkeypatch):
    region(monkeypatch)
    record = source()
    record['axis']['break_indices'] = [256]
    result = choose(record, [projected(1, [.1875, .3125]), projected(3, [.25, .375])])
    assert result['window_index'] == 3
    assert result['window_selection']['candidate_count'] == 1


@pytest.mark.parametrize('loop', ['', 'AG', 'BG', 'CG'])
def test_automatic_selection_never_infers_loop_or_bypasses_ground_compensation(monkeypatch, loop):
    region(monkeypatch)
    result = select_projection_window(source(), {}, {'mappings': {}, 'fault_loop': loop},
                                      [projected(2, [.1875, .3125])])
    assert result['status'] == 'Not available' and result['distance_km'] is None
    assert not result['authorizes_location']
    assert 'loop' in result['reason'].lower()
    if loop:
        assert 'compensation' in result['reason'].lower()


def test_detector_receives_same_source_bound_meanings_and_asserted_states(monkeypatch):
    calls = region(monkeypatch)
    record, item = source(), {'channel_inventory': [{'id': 'A1'}]}
    options = dict(mappings={'A1': 'VA'}, asserted_states={'D1': 0}, fault_loop='AB')
    select_projection_window(record, item, options, [projected(2, [.1875, .3125])])
    assert calls[0][0] is record and calls[0][1] is item
    assert calls[0][2] == dict(mappings={'A1': 'VA'}, asserted_states={'D1': 0})


def test_explicit_manual_window_stays_available_with_outside_fault_warning(monkeypatch):
    region(monkeypatch)
    rows = [projected(0, [0., .125], 20), projected(2, [.1875, .3125], 10)]
    result = choose(source(), rows, projection_window=0)
    assert result['window_index'] == 0 and result['distance_km'] == 20
    assert result['window_selection']['mode'] == 'manual'
    assert 'outside' in result['window_selection']['warning'].lower()
    assert not result['authorizes_location']


def test_manual_window_without_detected_event_retains_its_provenance(monkeypatch):
    region(monkeypatch, None)
    result = choose(source(), [projected(0, [0., .125])], projection_window=0)
    assert result['window_selection']['mode'] == 'manual'
    assert result['window_selection']['warning']
    assert result['distance_km'] == 10 and not result['authorizes_location']


def test_stale_manual_index_has_specific_unavailable_reason(monkeypatch):
    region(monkeypatch)
    result = choose(source(), [projected(0, [0., .125])], projection_window=100)
    assert result['status'] == 'Not available' and result['distance_km'] is None
    assert result['window_selection']['mode'] == 'manual'
    assert '100' in result['reason'] or 'available' in result['reason'].lower()


def test_manual_override_cannot_restore_support_across_declared_gap(monkeypatch):
    region(monkeypatch)
    record = source()
    record['axis']['break_indices'] = [256]
    result = choose(record, [projected(2, [.1875, .3125])], projection_window=2)
    assert result['status'] == 'Not available' and result['distance_km'] is None
    assert 'declared source break' in result['reason']
    selection = result['window_selection']
    assert selection['mode'] == 'manual' and selection['status'] == 'unavailable'
    assert selection['requested_window_index'] == 2
    assert selection['requested_support_s'] == [.1875, .3125]
    assert not result['authorizes_location']


def event_revision(tmp_path, *, stop=.34, fault=True):
    """Public analytic phase steps; exact Z=1+j4 ohm, no field inputs."""
    root, revision, folder = analytic_revision(tmp_path)
    cfg = folder/'analytic.cfg'
    cfg.write_text(cfg.read_text().replace('1200,241', '1200,601'))
    rows = []
    for index in range(601):
        t = index/1200
        magnitude = 10 if fault and .12 <= t < stop else 1
        theta = 2*math.pi*50*t
        angles = [theta, theta-2*math.pi/3, theta+2*math.pi/3]
        current = [math.sqrt(2)*magnitude*math.cos(angle) for angle in angles]
        voltage = [math.sqrt(2)*magnitude*(math.cos(angle)-4*math.sin(angle)) for angle in angles]
        rows.append(','.join(map(str, [index+1, index*1e6/1200, *voltage, *current])))
    cfg.with_suffix('.dat').write_text('\n'.join(rows)+'\n')
    revision['files'] = [dict(name=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                              size=p.stat().st_size) for p in folder.iterdir()]
    return root, revision


MODEL = dict(length_km=50, x1_ohm_per_km=.4, r1_ohm_per_km=.1,
             provenance='Public analytic model; unverified field assumptions.')


def test_default_native_pipeline_selects_bounded_fault_window_and_snapshots_provenance(tmp_path):
    root, revision = event_revision(tmp_path)
    result = diagnose_source(root, revision, 'analytic.cfg', dict(line_model=MODEL, fault_loop='AB'))
    projection = result['selected_projection']
    assert projection['status'] == 'Conditional model projection', projection
    assert projection['distance_km'] == pytest.approx(10, abs=1e-5)
    selection = projection['window_selection']
    lo, hi = selection['fault_support_s']
    assert lo <= projection['support_s'][0] < projection['support_s'][1] <= hi
    assert selection['mode'] == 'automatic' and selection['status'] == 'selected'
    assert 'projection_window' not in result['options']
    assert result['snapshot']['selected_projection']['window_selection'] == selection
    assert not projection['authorizes_location'] and not result['snapshot']['authorizes_location']
    assert all(window['support_s'][1]-window['support_s'][0] == pytest.approx(.08)
               for window in result['windows'])


def test_default_native_pipeline_keeps_no_event_unavailable_without_manual_demand(tmp_path):
    root, revision = event_revision(tmp_path, fault=False)
    result = diagnose_source(root, revision, 'analytic.cfg', dict(line_model=MODEL, fault_loop='AB'))
    assert result['fit_coverage']['model_consistent'] > 0
    projection = result['selected_projection']
    assert projection['status'] == 'Not available' and projection['distance_km'] is None
    assert projection['window_selection']['mode'] == 'automatic'
    assert projection['window_selection']['status'] == 'unavailable'
    assert 'manual' not in projection['reason'].lower()
    assert result['snapshot']['sections']['observed']


def test_native_short_event_does_not_relax_existing_eighty_millisecond_support(tmp_path):
    root, revision = event_revision(tmp_path, stop=.178)
    result = diagnose_source(root, revision, 'analytic.cfg', dict(line_model=MODEL, fault_loop='AB'))
    projection = result['selected_projection']
    assert result['fit_coverage']['model_consistent'] > 0
    assert projection['status'] == 'Not available' and projection['distance_km'] is None
    lo, hi = projection['window_selection']['fault_support_s']
    assert hi-lo < .08
    assert projection['window_selection']['candidate_count'] == 0
    assert all(window['support_s'][1]-window['support_s'][0] == pytest.approx(.08)
               for window in result['windows'])


def test_default_native_pipeline_names_missing_line_model_without_manual_window_demand(tmp_path):
    root, revision = event_revision(tmp_path)
    result = diagnose_source(root, revision, 'analytic.cfg', dict(fault_loop='AB'))
    projection = result['selected_projection']
    assert projection['status'] == 'Not available' and projection['distance_km'] is None
    assert 'line length' in projection['reason'].lower()
    assert 'manual' not in projection['reason'].lower()
    assert projection['window_selection']['fault_support_s'] is not None
    assert not projection['authorizes_location']


def test_default_native_pipeline_names_counts_refusal_without_fabricating_scaling(tmp_path):
    root, revision = event_revision(tmp_path)
    folder = __import__('pathlib').Path(revision['bundle']['root'])
    cfg = folder/'analytic.cfg'
    lines = cfg.read_text().splitlines()
    for index in range(2, 8):
        fields = lines[index].split(',')
        fields[4] = 'counts'
        lines[index] = ','.join(fields)
    cfg.write_text('\n'.join(lines)+'\n')
    revision['files'] = [dict(name=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                              size=p.stat().st_size) for p in folder.iterdir()]
    result = diagnose_source(root, revision, 'analytic.cfg', dict(line_model=MODEL, fault_loop='AB'))
    projection = result['selected_projection']
    assert projection['status'] == 'Not available' and projection['distance_km'] is None
    assert 'raw counts' in projection['reason'].lower()
    assert 'manual' not in projection['reason'].lower()
    assert all(channel['units'] == 'raw counts' for channel in result['channels'])
    assert not result['assumptions'] and not projection['authorizes_location']
