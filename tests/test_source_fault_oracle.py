"""Independent electrical laws catch wrong source and physical fault stamps."""
import importlib

import numpy as np
import pytest

from tests.section_network_oracle import solve as prior_slg

SECTIONS = [(40, .03+.25j, .4+1.4j), (60, .3+.7j, .1+1j)]
FAULTS = ('AG', 'BG', 'CG', 'AB', 'BC', 'CA', 'ABG', 'BCG', 'CAG', 'ABC', 'ABCG')


def oracle():
    return importlib.import_module('tests.source_fault_oracle')


@pytest.mark.parametrize('fault', FAULTS)
@pytest.mark.parametrize('profile', ['baseline', 'weak_R_10000', 'phase_impedance'])
def test_source_ohm_laws_and_physical_fault_contacts(fault, profile):
    sources = oracle().source_pair(profile)
    state = oracle().solve(SECTIONS, 40, fault, 5, sources=sources)
    for end, source in zip(('S', 'R'), sources, strict=True):
        np.testing.assert_allclose(state['V'+end]+source['z']@state['I'+end], source['emf'], atol=1e-7)
    phases = [i for i, p in enumerate('ABC') if p in fault]
    currents, voltage = state['fault_currents'], state['voltages'][state['fault_node']]
    np.testing.assert_allclose(currents, state['IS']+state['IR'], atol=1e-7)
    for i in set(range(3))-set(phases):
        assert abs(currents[i]) < 1e-8
    if len(phases) == 1:
        assert currents[phases[0]] == pytest.approx(voltage[phases[0]]/5, abs=1e-7)
    elif len(phases) == 2 and 'G' not in fault:
        a, b = phases
        assert currents[a] == pytest.approx((voltage[a]-voltage[b])/5, abs=1e-7)
        assert currents[b] == pytest.approx(-currents[a], abs=1e-7)
    else:
        contact = 2.5 if len(phases) == 2 else 5
        q = state['fault_bus_voltage']
        np.testing.assert_allclose(voltage[phases]-contact*currents[phases], q, atol=1e-7)
        assert sum(currents) == pytest.approx(q/5 if 'G' in fault else 0, abs=1e-7)
    assert state['residual'] < 1e-6


@pytest.mark.parametrize('fault', FAULTS)
def test_physical_reversal_swaps_source_facts_and_terminal_quantities(fault):
    sources = oracle().source_pair('voltage_unbalance')
    forward = oracle().solve(SECTIONS, 75, fault, sources=sources)
    reverse = oracle().solve(SECTIONS[::-1], 25, fault, sources=sources, reverse_sources=True)
    for key, other in [('VS', 'VR'), ('IS', 'IR'), ('VR', 'VS'), ('IR', 'IS')]:
        np.testing.assert_allclose(forward[key], reverse[other], atol=1e-7)


@pytest.mark.parametrize('phase', range(3))
def test_prior_single_phase_oracle_limit_is_unchanged(phase):
    new = oracle().solve(SECTIONS, 75, 'ABC'[phase]+'G')
    old = prior_slg(SECTIONS, 75, phase)
    for name in ('VS', 'IS', 'VR', 'IR'):
        np.testing.assert_allclose(new[name], old[name], atol=1e-7)


@pytest.mark.parametrize('fault', ['NONE', 'ABC', 'ABCG'])
def test_balanced_source_controls_have_no_material_negative_sequence(fault):
    state = oracle().solve(SECTIONS, 75, fault)
    for key in ('VS', 'VR', 'IS', 'IR'):
        assert abs(oracle().sequence(state[key], 2)) < 1e-8


def test_weak_source_reduces_remote_fault_infeed_and_source_asymmetry_is_material():
    normal = oracle().solve(SECTIONS, 75)
    weak = oracle().solve(SECTIONS, 75, sources=oracle().source_pair('weak_R_10000'))
    ratio = abs(oracle().sequence(weak['IR'], 2))/abs(oracle().sequence(weak['IS'], 2))
    assert ratio < .001
    assert np.linalg.norm(weak['IR']) < .001*np.linalg.norm(normal['IR'])
    unbalanced = oracle().solve(SECTIONS, 75, 'NONE', sources=oracle().source_pair('voltage_unbalance'))
    assert abs(oracle().sequence(unbalanced['VS'], 2)) > 100
    for profile in oracle().PROFILES:
        for source in oracle().source_pair(profile):
            assert min(np.linalg.eigvalsh(source['z'].real)) > 0
            assert min(np.linalg.eigvalsh(source['z'].imag)) > 0


@pytest.mark.parametrize('problem', ['fault', 'resistance', 'chainage', 'local bus', 'remote bus',
                                   'sections', 'source shape', 'nonfinite', 'active source'])
def test_invalid_network_definitions_raise_instead_of_silently_dropping_cases(problem):
    sections, km, fault, resistance = SECTIONS, 40, 'AG', 4
    sources = oracle().source_pair()
    if problem == 'fault':
        fault = 'ADG'
    elif problem == 'resistance':
        resistance = 0
    elif problem == 'chainage':
        km = 101
    elif problem == 'local bus':
        km = 0
    elif problem == 'remote bus':
        km = 100
    elif problem == 'sections':
        sections = [(-1, .1+1j, .2+2j)]
    elif problem == 'source shape':
        sources[0]['z'] = np.eye(2)
    elif problem == 'nonfinite':
        sources[1]['emf'][0] = np.nan
    else:
        sources[0]['z'] = -np.eye(3)+1j*np.eye(3)
    with pytest.raises(ValueError):
        oracle().solve(sections, km, fault, resistance, sources=sources)
