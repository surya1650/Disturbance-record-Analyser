"""Declared DAT offsets preserve chronology provenance without changing elapsed time."""
import json

import numpy as np
import pytest

from dranalyser.comtrade.source_time import digital_source_intervals, source_time_axis


def axis(stamps, **options):
    arguments = dict(nrates=0, timemult=1)
    arguments.update(options)
    return source_time_axis(list(range(1, len(stamps)+1)), stamps, **arguments)


def test_original_nonzero_dat_offsets_and_multiplier_are_retained_separately():
    first = 10**12
    result = axis([first, first+100, first+300], timemult=10)
    assert result['elapsed_s'] == pytest.approx([0, .001, .003])
    assert result['declared_origin'] == dict(status='available',
        first_offset_s=pytest.approx(10**7, rel=0, abs=1e-8),
        last_offset_s=pytest.approx(10**7+.003, rel=0, abs=1e-8),
        basis='Original DAT timestamps × declared time multiplier')
    assert result['alignment_eligible'] is result['authorizes_dsp'] is result['authorizes_location'] is False
    assert result['recorder_accuracy_verified'] is False
    json.dumps(result, allow_nan=False)


def test_zero_origin_is_preserved_without_changing_source_coordinates():
    result = axis([0, 1000, 2500])
    assert result['declared_origin']['first_offset_s'] == 0
    assert result['declared_origin']['last_offset_s'] == pytest.approx(.0025)
    assert result['elapsed_s'] == pytest.approx([0, .001, .0025])


@pytest.mark.parametrize('stamps,options', [
    ([0, 1000, 2000], dict(nrates=1)),
    ([0, 1000, 2000], dict(timemult=0)),
    ([0, 1000, 2000], dict(timemult=True)),
    ([0, 1000, 2000], dict(timemult=float('inf'))),
    ([0, 1000, 2000], dict(timemult=1e-320)),
    ([0, 1000, 1000], {}),
    ([0, 1000, np.nan], {}),
    ([-1, 1000, 2000], {}),
    ([0, 1], {}),
])
def test_withheld_source_axis_never_carries_origin_authority(stamps, options):
    result = axis(stamps, **options)
    assert result['status'] == 'withheld'
    assert 'declared_origin' not in result


@pytest.mark.parametrize('stamps,multiplier', [
    ([10**7, 10**7+1, 10**7+2], 1e308),
    ([1e-10, 1e6, 2e6], 1e-300),
])
def test_unrepresentable_original_offsets_do_not_remove_valid_elapsed_inspection(stamps, multiplier):
    result = axis(stamps, timemult=multiplier)
    assert result['status'] == 'source_time_inspection'
    assert result['elapsed_s'][0] == 0
    assert all(np.isfinite(value) for value in result['elapsed_s'])
    assert 'declared_origin' not in result
    json.dumps(result, allow_nan=False)


def test_invalid_digital_states_do_not_retain_a_valid_axis_origin():
    result = digital_source_intervals([1, 2, 3], [1000, 2000, 3000],
        [0, None, 1], nrates=0, timemult=1)
    assert result['status'] == 'withheld'
    assert 'declared_origin' not in result


def test_different_original_offsets_keep_identical_elapsed_observations():
    first = axis([0, 1000, 3000])
    later = axis([1e9, 1e9+1000, 1e9+3000])
    assert first['elapsed_s'] == later['elapsed_s']
    assert first['raw_period_runs'] == later['raw_period_runs']
    assert first['declared_origin']['first_offset_s'] == 0
    assert later['declared_origin']['first_offset_s'] == 1000
