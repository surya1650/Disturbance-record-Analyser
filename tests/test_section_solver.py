"""Physical nodal truth detects wrong section propagation and root selection."""
import importlib
import json

import numpy as np
import pytest

from tests.section_network_oracle import negative, solve
from tests.test_model_domain import MIXED, definition


def solver():
    return importlib.import_module('dranalyser.faultloc.sections')


def quantities(sections, km, phase=0, resistance=4, rotation=0, reverse=False):
    state = solve(sections, km, phase=phase, resistance=resistance, reverse_sources=reverse)
    values = [negative(state[k]) for k in ('VS', 'IS', 'VR', 'IR')]
    values[2:] = [v*np.exp(1j*rotation) for v in values[2:]]
    return values


@pytest.mark.parametrize('km', [1, 39.9, 40, 40.1, 75, 99])
@pytest.mark.parametrize('phase', [0, 1, 2])
@pytest.mark.parametrize('aligned,rotation', [(True, 0), (False, 0), (False, 2.1)])
def test_mixed_sections_recover_nodal_chainage_and_physical_reversal(km, phase, aligned, rotation):
    for sections, position, reverse in [(MIXED, km, False), (MIXED[::-1], 100-km, True)]:
        result = solver().section_window(definition(sections),
            *[[v]*8 for v in quantities(sections, position, phase, 50, rotation, reverse)], aligned=aligned)
        assert result['status'] == 'located', result
        assert result['km_from_S'] == pytest.approx(position, abs=1e-7)
        json.dumps(result, allow_nan=False)


def test_junction_is_one_candidate_but_distinct_unsynchronised_roots_are_not_chosen():
    result = solver().section_candidates(definition(MIXED), *quantities(MIXED, 40))
    assert result['status'] == 'unique' and result['candidates'][0]['section_sequences'] == [1, 2]
    line = definition([(1, 1+1j, 2+3j)])
    # |.9-2u| = |-.3+u| has two distinct, defined roots .4 and .6.
    result = solver().section_candidates(line, .9, 2/(1+1j), .7, 1/(1+1j))
    assert result['status'] == 'ambiguous'
    assert [c['km_from_S'] for c in result['candidates']] == pytest.approx([.4, .6])
    result = solver().section_window(line, [.9]*8, [2/(1+1j)]*8, [.7]*8, [1/(1+1j)]*8)
    assert result['status'] == 'withheld' and result['km_from_S'] is None


@pytest.mark.parametrize('problem', ['review', 'coupling', 'capacitor', 'shunt', 'gap', 'duplicate', 'empty', 'nan'])
def test_unsupported_models_refuse_without_numeric_output(problem):
    line = definition(MIXED)
    if problem == 'review':
        line.model_review_required = True
    elif problem == 'coupling':
        line.double_circuit = True
    elif problem == 'capacitor':
        line.series_compensated = True
    elif problem == 'shunt':
        line.sections[0].b0 = 1e-6
    elif problem == 'gap':
        line.sections[1].from_km += .001
    elif problem == 'duplicate':
        line.sections[1].seq = line.sections[0].seq
    elif problem == 'empty':
        line.sections = []
    else:
        line.sections[0].x1 = np.nan
    result = solver().section_window(line, *[[v]*8 for v in quantities(MIXED, 75)])
    assert result['status'] == 'withheld' and result['m'] is None and result['km_from_S'] is None
    assert result['reason']
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('problem', ['short', 'unequal', 'nonfinite', 'zero', 'angle drift', 'distance drift', 'one bad sample'])
def test_invalid_or_nonstationary_windows_never_discard_bad_samples(problem):
    values = np.array([[v]*8 for v in quantities(MIXED, 75)])
    if problem == 'short':
        values = values[:, :1]
    elif problem == 'unequal':
        values = [*values[:3], values[3, :-1]]
    elif problem == 'nonfinite':
        values[0, 3] = np.nan
    elif problem == 'zero':
        values[:] = 0
    elif problem == 'angle drift':
        values[2:] *= np.exp(1j*np.linspace(0, 1, 8))
    elif problem == 'distance drift':
        values[:, 4:] = np.array([[v]*4 for v in quantities(MIXED, 20)])
    else:
        values[0, 3] *= 1e6
    result = solver().section_window(definition(MIXED), *values)
    assert result['status'] == 'withheld' and result['km_from_S'] is None, result


@pytest.mark.parametrize('scale', [1e-7, 1, 1e7])
def test_common_scaling_preserves_section_distance(scale):
    values = [[v*scale]*8 for v in quantities(MIXED, 75, rotation=-2.7)]
    result = solver().section_window(definition(MIXED), *values)
    assert result['status'] == 'located', result
    assert result['km_from_S'] == pytest.approx(75, abs=1e-7)
