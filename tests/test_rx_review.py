"""Independent circuit/display oracles and refusal contracts; not field validation."""
import copy
import json

import numpy as np
import pytest

from dranalyser.application.intake import metadata_value
from dranalyser.dsp.pipeline import analyse
from dranalyser.registry.settings import PolygonChar, ProtectionSettings, Zone
from dranalyser.registry.settings_io.rio import parse_rio
from dranalyser.report.navigation import navigation_record
from dranalyser.rules.evidence import relay_evidence
from dranalyser.workbench.rx_review import CONFIRMATIONS, clean_rx_review
from tests.test_navigation import analysed_wave
from tests.test_settings import RIO_FIXTURE


def inputs():
    an = analysed_wave()
    an.record.content_hash = 'a'*64
    settings = parse_rio(RIO_FIXTURE)
    settings.zones[0].earth = PolygonChar(kind='earth', vertices=[(0, 0), (9, 0), (9, 4), (0, 4)])
    binding = {'status': 'associated export', 'sha256': 'b'*64, 'file': 'event.rio'}
    review = clean_rx_review(dict(record_hash='a'*64, settings_hash='b'*64, reviewer='Synthetic fixture',
                                  reason='Independent circuit fixture; no field assertion.', ct_ratio=1000, vt_ratio=2500,
                                  **dict.fromkeys(CONFIRMATIONS, True)))
    return an, settings, binding, review


def nav(an, settings, binding, review):
    return navigation_record(an, relay_evidence(an, 'event.cfg'), settings, binding, review)['rx']


@pytest.mark.parametrize('rotation', [0, .7])
def test_ground_loops_match_independent_self_mutual_circuit_and_ignore_neutral_channel(rotation):
    an, settings, binding, review = inputs()
    # Independent phase-domain series network: Zself=10+j18, Zmutual=5+j6.
    # Its positive sequence impedance is Zself-Zmutual = 5+j12 ohm.
    # The zero-sequence impedance is Zself+2*Zmutual = 20+j30 ohm.
    currents = np.array([10+2j, -1+3j, 4-1j])*np.exp(1j*rotation)
    voltages = np.array([(10+18j)*i+(5+6j)*sum(currents[j] for j in range(3) if j != n)
                         for n, i in enumerate(currents)])
    for n, phase in enumerate('ABC'):
        for prefix, values in [('I', currents), ('V', voltages)]:
            an.record.analog[prefix+phase] = np.sqrt(2)*np.real(values[n]*np.exp(2j*np.pi*50*an.record.t))
    an.record.analog['IN'] = np.full(an.record.n, -9999.)  # must not replace the phase residual
    settings.k0_params = {'re_rl': 1., 'xe_xl': .5}
    settings.line_angle_deg = np.degrees(np.arctan2(12, 5))
    an = analyse(an.record)
    before = copy.deepcopy(an.ps.phasors)
    result = nav(an, settings, binding, review)
    assert set(result['loops']) == {'AB', 'BC', 'CA', 'AG', 'BG', 'CG'}
    for name in ('AG', 'BG', 'CG'):
        points = result['loops'][name]
        assert all(p[1] is None for p in points[:an.ps.n_window])
        good = np.array([p[1:] for p in points if p[1] is not None])
        assert good[:, 0] == pytest.approx(5, abs=1e-7)
        assert good[:, 1] == pytest.approx(12, abs=1e-7)
    for key in before:
        np.testing.assert_equal(an.ps.phasors[key], before[key])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('key', ['record_hash', 'settings_hash', 'channel_mapping'])
def test_review_cannot_survive_source_or_mapping_change(key):
    args = inputs()
    args[3][key] = {'record_hash': 'c'*64, 'reason': 'different mapping'} if key == 'channel_mapping' else 'c'*64
    result = nav(*args)
    assert set(result['loops']) == {'AB', 'BC', 'CA'}
    assert not result['zones']['phase'] and not result['zones']['earth']
    assert any('stale' in v for v in result['context']['ground_missing'])


@pytest.mark.parametrize('key', CONFIRMATIONS)
def test_each_confirmation_is_a_gate_and_zero_sequence_is_ground_specific(key):
    args = inputs()
    args[3][key] = False
    result = nav(*args)
    assert 'AG' not in result['loops']
    assert bool(result['zones']['phase']) == (key == 'zero_sequence_voltage')


@pytest.mark.parametrize('problem', ['missing', 'ambiguous', 'angle', 'native', 'nonfinite', 'correction', 'scaling', 'gap'])
def test_ground_prerequisite_failures_keep_phase_view_or_explicit_refusal(problem):
    an, settings, binding, review = inputs()
    if problem == 'missing':
        settings = None
    elif problem == 'ambiguous':
        binding['status'] = 'ambiguous'
    elif problem == 'angle':
        settings.unknown.append('line_angle_deg')
    elif problem == 'native':
        del settings.k0_params['re_rl']
    elif problem == 'nonfinite':
        settings.k0_params['re_rl'] = float('inf')
    elif problem == 'correction':
        settings.impedance_correction = True
    elif problem == 'scaling':
        an.record.analog_meta['IA'].normalised = False
    elif problem == 'gap':
        an.record.t[200:] += .01
    result = nav(an, settings, binding, review)
    assert 'AG' not in result['loops']
    assert result['context']['ground_missing']
    json.dumps(result, allow_nan=False)
    if problem in ('scaling', 'gap'):
        assert not result['loops'] and not result['zones']['phase']


def test_settings_boundary_uses_vt_over_ct_and_never_borrows_characteristic_kind():
    an, settings, binding, review = inputs()
    settings.zones.append(Zone(name='Earth only', earth=PolygonChar(kind='earth', vertices=[(0, 0), (2, 0), (2, 2)])))
    result = nav(an, settings, binding, review)
    assert result['context']['primary_ohm_per_secondary_ohm'] == 2.5
    assert result['zones']['phase'][0]['points'][1] == pytest.approx([15.085, 0])
    assert result['zones']['earth'][0]['points'][1] == [22.5, 0]
    assert [z['name'] for z in result['zones']['phase']] == ['Z1']
    assert [z['name'] for z in result['zones']['earth']] == ['Z1', 'Earth only']
    assert any('Earth only phase' in v for v in result['zones']['omitted'])
    review['ct_ratio'] = None
    result = nav(an, settings, binding, review)
    assert 'AG' in result['loops'] and not result['zones']['phase']


def test_invalid_boundary_is_withheld_without_erasing_valid_phase_view():
    args = inputs()
    args[1].zones[0].earth.vertices = [(0, 0), (1, 1), (2, 2)]
    result = nav(*args)
    assert result['zones']['phase'] and not result['zones']['earth']
    assert 'invalid outline' in result['zones']['omitted'][0]


def test_zero_compensation_is_valid_but_direct_complex_entry_is_unsupported():
    args = list(inputs())
    args[1].k0_params = dict(re_rl=0, xe_xl=0)
    assert nav(*args)['context']['k0'] == [0, 0]
    args[1] = ProtectionSettings(k0_convention='complex_k0', k0_params={'k0_real': .8, 'k0_imag': 0})
    assert 'AG' not in nav(*args)['loops']


@pytest.mark.parametrize('change', [{'ct_ratio': 0}, {'vt_ratio': float('nan')}, {'ct_ratio': True},
                                    {'phase_scaling_polarity': 'true'}, {'reviewer': ''}, {'settings_hash': 'bad'},
                                    {'k0': .8}, {'reason': 'x'*1001}])
def test_invalid_review_metadata_is_rejected_at_intake(change):
    review = inputs()[3] | change
    with pytest.raises(ValueError, match='R-X'):
        metadata_value({'assignments': {'a.cfg': {'end': 'S', 'role': 'primary', 'rx_review': review}}})
