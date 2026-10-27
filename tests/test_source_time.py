"""Breaks: invented uniform time, false digital edges and coercive input acceptance."""
import importlib
import json

import numpy as np
import pytest


def call(stamps=(0, 1000, 2500, 4000, 6000), numbers=None, states=None, **opts):
    api = importlib.import_module('dranalyser.comtrade.source_time')
    numbers = list(range(1,len(stamps)+1)) if numbers is None else numbers
    kwargs = dict(nrates=0, timemult=1)
    kwargs.update(opts)
    out = (api.source_time_axis(numbers, stamps, **kwargs) if states is None else
           api.digital_source_intervals(numbers, stamps, states, **kwargs))
    json.dumps(out, allow_nan=False)
    assert out['authorizes_dsp'] is out['authorizes_location'] is out['alignment_eligible'] is False
    assert out['recorder_accuracy_verified'] is False
    return out


def test_irregular_source_times_are_preserved_without_uniformization():
    out = call()
    assert out['status'] == 'source_time_inspection'
    assert out['elapsed_s'] == pytest.approx([0,.001,.0025,.004,.006])
    assert [r['interval_count'] for r in out['raw_period_runs']] == [1,2,1]


def test_transition_brackets_and_duration_come_from_actual_source_times():
    out = call(states=[0,1,1,0,0])
    segment = out['intervals'][0]
    assert segment['start_source_s'] == .001 and segment['end_source_s'] == .004
    assert segment['source_span_s'] == pytest.approx(.003)
    assert segment['duration_sample_bracket_s'] == pytest.approx([.0015,.004])


def test_initial_and_final_active_states_never_invent_edges():
    a = call(states=[1,1,0,0,1])['intervals']
    assert a[0]['start_source_s'] is None and a[0]['source_span_s'] is None
    assert a[1]['end_source_s'] is None and a[1]['duration_sample_bracket_s'] is None


def test_large_gap_is_visible_and_never_authorizes_acquisition():
    out = call(stamps=[0,1000,1000000,1001000,1002000], states=[0,0,1,0,0])
    assert out['maximum_interval_s'] == pytest.approx(.999)
    assert out['intervals'][0]['duration_sample_bracket_s'] == pytest.approx([0,1])


@pytest.mark.parametrize('stamps', [[], [0,1], [0,0,1], [0,2,1], [0,np.nan,2],
    [0,np.inf,2], [0,True,2], ['0','1','2'], [0,1+1j,2], [[0],[1],[2]],
    [0,1e-320,2e-320], [0,1e308,1.7e308], [0,10**1000,10**1001]])
def test_bad_timestamps_withhold(stamps):
    assert call(stamps=stamps)['status'] == 'withheld'


@pytest.mark.parametrize('numbers', [[1,3,4,5,6], [1,1,2,3,4], [0,.5,1,2,3],
    [True,2,3,4,5], [2**53+i for i in range(5)]])
def test_bad_sample_numbers_withhold(numbers):
    assert call(numbers=numbers)['status'] == 'withheld'


@pytest.mark.parametrize('opts', [dict(nrates=True),dict(nrates=1),dict(timemult=0),
    dict(timemult=-1),dict(timemult=True),dict(timemult=np.nan),dict(timemult=1e-320),dict(timemult=10**1000)])
def test_invalid_controls_withhold(opts):
    api = importlib.import_module('dranalyser.comtrade.source_time')
    args = dict(nrates=0,timemult=1)
    args.update(opts)
    assert api.source_time_axis([1,2,3],[0,1000,2000],**args)['status'] == 'withheld'


@pytest.mark.parametrize('states', [[0,1], [0,1,2,0,0], [0,np.nan,1,0,0], ['0']*5, [False]*5])
def test_unknown_or_bad_digital_states_withhold(states):
    assert call(states=states)['status'] == 'withheld'


def test_explicit_multiplier_and_large_origin():
    out = call(stamps=[1e12,1e12+100,1e12+300], timemult=10)
    assert out['elapsed_s'] == pytest.approx([0,.001,.003])


@pytest.mark.parametrize('category', ['numbers', 'stamps', 'states'])
def test_masked_observations_cannot_become_observed_values(category):
    a = importlib.import_module('dranalyser.comtrade.source_time')
    data = dict(numbers=[1,2,3,4,5], stamps=[0,1000,2000,3000,4000], states=[0,1,1,0,0])
    data[category] = np.ma.array(data[category], mask=[0,1,0,0,0])
    assert a.digital_source_intervals(**data, nrates=0, timemult=1)['status'] == 'withheld'


@pytest.mark.parametrize('category', ['numbers', 'stamps', 'states'])
def test_explicitly_unmasked_observations_remain_inspectable(category):
    a = importlib.import_module('dranalyser.comtrade.source_time')
    data = dict(numbers=[1,2,3,4,5], stamps=[0,1000,2000,3000,4000], states=[0,1,1,0,0])
    data[category] = np.ma.array(data[category], mask=False)
    assert a.digital_source_intervals(**data, nrates=0, timemult=1)['status'] == 'source_time_inspection'


@pytest.mark.parametrize('multiplier,stamps', [
    (3e-318,[0,10**12,2*10**12]),
    (1e-300,[0,1e-9,2e-9]),
])
def test_nonzero_subnormal_conversion_cannot_distort_source_coordinates(multiplier, stamps):
    assert call(stamps=stamps, timemult=multiplier)['status'] == 'withheld'
