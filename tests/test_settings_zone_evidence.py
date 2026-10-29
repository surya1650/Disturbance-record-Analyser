"""A project timer/default or the other terminal's settings is not relay evidence."""
import numpy as np
import pytest

from dranalyser.dsp.pipeline import analyse
from dranalyser.registry.settings import ProtectionSettings, Zone
from dranalyser.rules.features import incident_features, terminal_features
from dranalyser.synth.generator import SynthSpec, TerminalSpec, generate


@pytest.fixture
def analyses():
    case = generate(SynthSpec(S=TerminalSpec(trip_delay_s=.35, breaker_time_s=.40, post_s=.8),
                              R=TerminalSpec(trip_delay_s=.35, breaker_time_s=.40, post_s=.8)))
    return {end: analyse(record) for end, record in case.records.items()}


def test_missing_settings_never_infer_zone_from_default_timer(analyses):
    features = terminal_features(analyses['S'], 'S', z2_time_s=.35).values
    assert features['operate_ms'] is not None
    assert features['zone_operated'] is None
    assert features['zone_timer_s'] is None
    assert features['zone_timer_source'] == 'Not supplied'


def test_two_terminals_use_only_their_own_actual_zone_timer(analyses):
    settings = {'S': ProtectionSettings(zones=[Zone('Z2', t1=.35)]),
                'R': ProtectionSettings(zones=[Zone('Z2', t1=.8)])}
    features = incident_features(analyses, settings=settings, z2_time_s=.01)
    assert features['S_zone_operated'] == 'Z2'
    assert features['R_zone_operated'] == 'Z1_OR_AIDED'
    assert features['S_zone_timer_s'] == .35 and features['R_zone_timer_s'] == .8
    missing = incident_features(analyses, settings={'S': settings['S']}, z2_time_s=.35)
    assert missing['R_zone_operated'] is None and missing['R_zone_timer_s'] is None


def test_explicit_zone_trip_contact_survives_without_settings(analyses):
    analysis = analyses['S']
    analysis.record.digital['TRIP Z2'] = np.array(analysis.record.digital['TRIP'], copy=True)
    features = terminal_features(analysis, 'S').values
    assert features['zone_operated'] == 'Z2'
    assert features['zone_timer_s'] is None


@pytest.mark.parametrize('timer', [None, 'unknown', 0, -1, float('inf'), float('nan')])
def test_invalid_or_missing_zone_timer_cannot_grade_operating_time(analyses, timer):
    settings = ProtectionSettings(zones=[Zone('Z2', t1=timer)])
    assert terminal_features(analyses['S'], 'S', settings).values['zone_operated'] is None
    assert terminal_features(analyses['S'], 'S', ProtectionSettings()).values['zone_operated'] is None
