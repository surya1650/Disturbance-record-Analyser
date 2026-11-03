"""Technical report R-X uses the same source-bound display gates as navigation."""
import copy
import re

import pytest

from dranalyser.registry.settings import MhoChar, PolygonChar, Zone
from dranalyser.report import render
from dranalyser.report.graphics import rx_diagram
from dranalyser.report.rx_context import display_context
from dranalyser.rules.evidence import relay_evidence
from tests.test_report import _synth_report
from tests.test_rx_review import inputs


def reviewed():
    an, settings, binding, review = inputs()
    binding['sha256'] = settings.provenance.sha256
    review['settings_hash'] = binding['sha256']
    ev = relay_evidence(an, 'event.cfg', 'S', 'primary')
    ev['rx_context'] = display_context(an, settings, binding, review)
    return an, settings, ev


def test_render_withholds_unreviewed_settings_and_ground_trajectory(monkeypatch):
    rep = _synth_report(two_ended=False)
    _, settings, _, _ = inputs()
    rep.settings = {'S': settings}
    seen = {}

    def capture(zones, trajectory, angle, *args, **kwargs):
        seen.update(zones=zones, trajectory=trajectory)
        return '<p>R-X captured</p>'

    monkeypatch.setattr('dranalyser.report.graphics.rx_diagram', capture)
    html = render(rep)
    assert not seen['zones'] and not seen['trajectory']
    assert 'No per-record R-X input review supplied.' in html
    assert 'data-rx-display-version="2"' in html
    assert 'primary ohm' in html


def test_valid_review_matches_navigation_and_accepts_zero_compensation():
    from dranalyser.report.static_rx import rx_model
    from dranalyser.report.navigation import phase_loops
    an, settings, ev = reviewed()
    an.fault_type = 'AG'
    settings.k0_params = {'re_rl': 0, 'xe_xl': 0}
    model = rx_model(an, 'S', settings, [ev])
    assert model['context']['k0'] == [0, 0]
    assert model['trajectory'] and model['zones']
    expected = phase_loops(an, context=model['context'])['loops']['AG']
    lo = float(an.notes.get('inception_t', 0))
    expected = [complex(r, x) if r is not None and x is not None else None
                for t, r, x in expected if lo <= t < lo + 6/an.freq]
    assert model['trajectory'] == expected


@pytest.mark.parametrize('problem', ['absent', 'record', 'end', 'role', 'duplicate', 'settings', 'mapping',
                                     'identity', 'effective', 'polarity', 'review_record', 'review_settings', 'forged', 'malformed'])
def test_absent_stale_and_forged_context_never_unlocks_ground_or_zones(problem):
    from dranalyser.report.static_rx import rx_model
    an, settings, ev = reviewed()
    an.fault_type = 'AG'
    evidence = [ev]
    if problem == 'absent':
        ev.pop('rx_context')
    elif problem == 'record':
        ev['record_hash'] = 'c'*64
    elif problem == 'end':
        ev['end'] = 'R'
    elif problem == 'role':
        ev['role'] = 'corroborating'
    elif problem == 'duplicate':
        evidence.append(copy.deepcopy(ev))
    elif problem == 'settings':
        settings.provenance.sha256 = 'c'*64
    elif problem == 'mapping':
        an.record.notes['channel_mapping'] = {'record_hash': 'c'*64, 'reason': 'changed'}
    elif problem in ('identity', 'effective', 'polarity'):
        key = {'identity': 'settings_identity', 'effective': 'effective_at_event',
               'polarity': 'phase_scaling_polarity'}[problem]
        ev['rx_context']['review'][key] = False
    elif problem in ('review_record', 'review_settings'):
        key = 'record_hash' if problem == 'review_record' else 'settings_hash'
        ev['rx_context']['review'][key] = 'c'*64
    elif problem == 'forged':
        ev['rx_context'] = {'k0': [99, 0], 'primary_ohm_per_secondary_ohm': 1,
                            'ground_missing': [], 'zone_missing': []}
    else:
        ev['rx_context']['review'] = 'not a review'
    model = rx_model(an, 'S', settings, evidence)
    assert not model['trajectory'] and not model['zones']
    assert model['reasons']
    assert model['context']['k0'] is None


def test_phase_loop_survives_without_settings_or_physical_end_review():
    from dranalyser.report.static_rx import rx_model
    an, _, _ = reviewed()
    an.fault_type = 'AB'
    model = rx_model(an, 'S', None, [])
    assert any(value is not None for value in model['trajectory'])
    assert not model['zones'] and model['reasons']


def test_missing_native_ground_compensation_never_becomes_zero():
    from dranalyser.report.static_rx import rx_model
    an, settings, ev = reviewed()
    an.fault_type = 'AG'
    settings.k0_convention = ''
    settings.k0_params = {}
    model = rx_model(an, 'S', settings, [ev])
    assert model['context']['k0'] is None and not model['trajectory']
    assert any('compensation' in reason for reason in model['reasons'])


def test_exact_characteristic_kind_and_vendor_neutral_mho_outline():
    from dranalyser.report.static_rx import rx_model
    an, settings, ev = reviewed()
    an.fault_type = 'AB'
    settings.zones = [Zone(name='Phase mho', phase=MhoChar(diameter=5+15j)),
                      Zone(name='Earth only', earth=PolygonChar(vertices=[(0, 0), (4, 0), (4, 8)]))]
    phase = rx_model(an, 'S', settings, [ev])
    assert [zone['name'] for zone in phase['zones']] == ['Phase mho']
    assert len(phase['zones'][0]['vertices']) == 48
    # The reviewed impedance conversion is 2500/1000 = 2.5; vertices are primary ohm.
    assert phase['zones'][0]['vertices'][0] == pytest.approx([26.01423537605237, 18.75])
    an.fault_type = 'AG'
    ground = rx_model(an, 'S', settings, [ev])
    assert [zone['name'] for zone in ground['zones']] == ['Earth only']
    assert ground['zones'][0]['vertices'][1] == [10, 0]
    an.fault_type = 'ABG'
    assert rx_model(an, 'S', settings, [ev])['loop'] == 'AB'


@pytest.mark.parametrize('problem', ['gap', 'multirate', 'scaling'])
def test_unsupported_acquisition_withholds_trajectory_and_overlays(problem):
    from dranalyser.report.static_rx import rx_model
    an, settings, ev = reviewed()
    an.fault_type = 'AB'
    if problem == 'gap':
        an.record.t[200:] += .01
    elif problem == 'multirate':
        an.record.nrates = 2
    else:
        an.record.analog_meta['IA'].normalised = False
    model = rx_model(an, 'S', settings, [ev])
    assert not model['trajectory'] and not model['zones'] and model['reasons']


@pytest.mark.parametrize('last', [None, complex(float('nan'), 0), complex(0, float('inf'))])
def test_graphic_keeps_missing_segments_separate_and_drops_stale_last_marker(last):
    html = rx_diagram([], [1+2j, 2+3j, None, 4+5j, 5+6j, last], None, unit='primary ohm')
    assert html.count('<polyline') == 2
    assert 'measured' not in html
    assert 'R, primary ohm' in html and 'X, primary ohm' in html
    assert not re.search(r'\b(?:nan|inf)\b', html)


def test_zone_assessment_and_local_timing_labels_are_explicit():
    rep = _synth_report(two_ended=False)
    rep.features['S_zone_expected'] = None
    rep.features['S_zone_expected_reason'] = 'Review <actual> settings.'
    html = render(rep)
    assert 'Zone assessment' in html and 'Not assessed' in html
    assert 'Review &lt;actual&gt; settings.' in html
    assert 'Trip indication' in html and 'Trip-to-current-zero' in html


def test_missing_operational_phasors_remain_a_break_in_static_trajectory():
    from dranalyser.report.static_rx import rx_model
    an, settings, ev = reviewed()
    an.fault_type = 'AB'
    an.notes['inception_t'] = .05
    an.ps.phasors['IA'][90:110] = complex(float('nan'), 0)
    model = rx_model(an, 'S', settings, [ev])
    assert None in model['trajectory']
    html = rx_diagram(model['zones'], model['trajectory'], model['line_angle_deg'], unit='primary ohm')
    assert html.count('<polyline') == 2


def test_serialized_derived_values_cannot_replace_current_reviewed_inputs():
    from dranalyser.report.static_rx import rx_model
    an, settings, ev = reviewed()
    an.fault_type = 'AG'
    expected = rx_model(an, 'S', settings, [ev])
    ev['rx_context']['k0'] = [99, -99]
    ev['rx_context']['primary_ohm_per_secondary_ohm'] = 999
    ev['rx_context']['ground_missing'] = []
    ev['rx_context']['zone_missing'] = []
    actual = rx_model(an, 'S', settings, [ev])
    assert actual == expected


@pytest.mark.parametrize('value', [10**1000, float('nan'), float('inf'), 'not numeric', True])
def test_malformed_reviewed_ratio_refuses_overlay_without_crashing(value):
    from dranalyser.report.static_rx import rx_model
    an, settings, ev = reviewed()
    an.fault_type = 'AB'
    ev['rx_context']['review']['ct_ratio'] = value
    model = rx_model(an, 'S', settings, [ev])
    assert model['trajectory'] and not model['zones']
    assert any('ratios' in reason for reason in model['reasons'])


@pytest.mark.parametrize('value', [10**1000, float('nan'), float('inf'), 'not numeric', True])
def test_malformed_line_angle_never_draws_an_invented_direction(value):
    from dranalyser.report.static_rx import rx_model
    an, settings, ev = reviewed()
    an.fault_type = 'AB'
    settings.line_angle_deg = value
    model = rx_model(an, 'S', settings, [ev])
    assert model['line_angle_deg'] is None
    assert any('line angle' in reason for reason in model['reasons'])
