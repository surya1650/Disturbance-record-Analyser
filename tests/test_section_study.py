"""Aligned section search checked against an independent phase nodal network."""
import copy
import json

import numpy as np
import pytest

from dranalyser.faultloc.model_domain import scalar_model_reasons
from dranalyser.validation.section_study import aligned_section_candidates
from tests.section_network_oracle import negative, solve
from tests.test_model_domain import definition, MIXED


@pytest.mark.parametrize('km', [1, 39.9, 40, 40.1, 75, 99])
@pytest.mark.parametrize('phase', [0, 1, 2])
@pytest.mark.parametrize('resistance', [1, 50])
def test_aligned_mixed_section_search_recovers_independent_phase_network_chainage(km, phase, resistance):
    line = definition(MIXED)
    state = solve(MIXED, km, phase=phase, resistance=resistance)
    quantities = [negative(state[k]) for k in ('VS', 'IS', 'VR', 'IR')]
    result = aligned_section_candidates(line, *quantities)
    assert result['status'] == 'unique', result
    assert len(result['candidates']) == 1
    assert result['candidates'][0]['km_from_S'] == pytest.approx(km, abs=1e-7)
    assert scalar_model_reasons(line)  # study never authorizes the production model
    json.dumps(result, allow_nan=False)
    reverse = solve(MIXED[::-1], 100-km, phase=phase, resistance=resistance, reverse_sources=True)
    reversed_result = aligned_section_candidates(definition(MIXED[::-1]),
        *[negative(reverse[k]) for k in ('VS', 'IS', 'VR', 'IR')])
    assert reversed_result['status'] == 'unique'
    assert reversed_result['candidates'][0]['km_from_S'] == pytest.approx(100-km, abs=1e-7)


def test_physical_junction_is_one_candidate_with_both_section_locators():
    state = solve(MIXED, 40)
    result = aligned_section_candidates(definition(MIXED), *[negative(state[k]) for k in ('VS', 'IS', 'VR', 'IR')])
    assert result['status'] == 'unique'
    assert result['candidates'][0]['section_sequences'] == [1, 2]


@pytest.mark.parametrize('km', [5, 40, 95])
def test_uniform_and_proportional_section_limits_preserve_chainage(km):
    sections = [(40, .03+.25j, .1+.75j), (60, .06+.5j, .2+1.5j)]
    state = solve(sections, km)
    result = aligned_section_candidates(definition(sections), *[negative(state[k]) for k in ('VS', 'IS', 'VR', 'IR')])
    assert result['status'] == 'unique'
    assert result['candidates'][0]['km_from_S'] == pytest.approx(km, abs=1e-7)


@pytest.mark.parametrize('problem', ['coupling', 'shunt', 'compensated', 'geometry', 'nonfinite', 'unreviewed', 'missing'])
def test_section_study_refuses_unsupported_or_invalid_model_inputs(problem):
    line = definition(MIXED)
    if problem == 'coupling':
        line.double_circuit = True
    elif problem == 'shunt':
        line.sections[0].b1 = 1e-6
    elif problem == 'compensated':
        line.series_compensated = True
    elif problem == 'geometry':
        line.sections[1].from_km += 1
    elif problem == 'nonfinite':
        line.sections[0].x1 = np.nan
    elif problem == 'unreviewed':
        line.model_review_required = True
    else:
        line.sections = []
    result = aligned_section_candidates(line, 1, 1, 1, 1)
    assert result['status'] == 'withheld' and not result['candidates']
    assert result['reason']
    json.dumps(result, allow_nan=False)


def test_inconsistent_or_absent_sequence_cannot_produce_a_section_distance():
    line = definition(MIXED)
    for quantities in [(1, 0, 1, 0), (complex(np.nan), 1, 1, 1), (1e6, 1, 1, 1)]:
        result = aligned_section_candidates(line, *quantities)
        assert result['status'] == 'withheld' and not result['candidates']


def test_uncertain_distinct_section_candidates_are_retained_without_automatic_selection():
    line = definition([(10, 1+.1j, 2+.3j), (10, .1+1j, .3+2j)])
    original = copy.deepcopy(line)
    # No exact network solution: two segment projections fit this intentionally
    # loose study tolerance. A numerical minimum must not hide the second one.
    result = aligned_section_candidates(line, 7-7j, 1, 0, 1, tolerance=.2)
    assert result['status'] == 'ambiguous' and len(result['candidates']) == 2
    assert result['candidates'][0]['km_from_S'] < 10 < result['candidates'][1]['km_from_S']
    assert line == original
