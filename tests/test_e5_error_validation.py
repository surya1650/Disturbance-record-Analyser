"""Independent source truth, retained denominators and immutable publication."""
import importlib
import json

import numpy as np
import pytest


def modules():
    return (importlib.import_module('tests.error_set_oracle'),
            importlib.import_module('scripts.e5_error_validation'))


def test_frozen_grid_is_complete_disjoint_and_has_separate_invalid_caps():
    oracle, _ = modules()
    grid = oracle.case_grid()
    assert len(grid) == len({json.dumps(c, sort_keys=True) for c in grid}) == 556
    assert sum(c['kind'] == 'direct' for c in grid) == 480
    assert sum(c['kind'] == 'nodal' for c in grid) == 60
    assert sum(c['kind'] == 'violated' for c in grid) == 16
    assert {c['seed'] for c in grid if c['kind'] == 'direct'} == {91631, 92743}


def test_oracle_obeys_common_fault_signs_and_declared_disks():
    oracle, _ = modules()
    grid = oracle.case_grid()
    chosen = [c for c in grid if c['kind'] == 'nodal']+[c for c in grid if c['kind'] == 'direct'][::11]
    for config in chosen:
        case = oracle.make_case(config)
        for support in case['supports']:
            vs, is_, vr, ir = support['truth']
            left = vs-case['left_impedance']*is_
            right = vr-(sum(z for _, z in case['sections'])-case['left_impedance'])*ir
            assert abs(abs(left)-abs(right)) <= 3e-9*max(abs(vs), abs(vr), 1)
            for measured, truth, cap in zip(support['measured'], support['truth'], support['caps'], strict=True):
                assert abs(measured-truth) <= cap*(1+1e-12)+1e-12
        assert case['caps_cover_truth'] is True


def test_nodal_oracle_sign_and_scale_cannot_be_replaced_by_scalar_truth():
    oracle, _ = modules()
    c = next(c for c in oracle.case_grid() if c['kind'] == 'nodal' and c['m'] == .42)
    case = oracle.make_case(c)
    vs, is_, vr, ir = case['supports'][0]['truth']
    assert not np.isclose(abs(vs-.42*sum(z for _, z in case['sections'])*is_),
                          abs(vr-(1-.42)*sum(z for _, z in case['sections'])*ir), rtol=1e-5)


def test_real_runner_keeps_full_line_for_weak_overlapping_caps():
    oracle, runner = modules()
    grid = [c for c in oracle.case_grid() if c['kind'] == 'direct' and c['profile'] == 'bothWeak'
            and c['caps'] == 'bounded'][:2]
    result = runner.run(grid=grid)
    assert result['evaluated'] == result['within_cap_cases'] == 2
    assert result['within_cap_truth_omissions'] == 0
    assert all(c['result']['status'] == 'uninformative' for c in result['cases'])
    assert result['authorizes_location'] is False
    assert result['protocol_complete'] is False
    assert 'tests/full_record_signals.py' in result['source_sha256_utf8_lf']
    json.dumps(result, allow_nan=False)


def test_invalid_caps_are_counted_but_not_used_as_successful_coverage():
    oracle, runner = modules()
    result = runner.run(grid=[c for c in oracle.case_grid() if c['kind'] == 'violated'])
    assert result['planned'] == result['evaluated'] == result['violated_cap_cases'] == 16
    assert result['within_cap_cases'] == 0
    assert all(c['caps_cover_truth'] is False for c in result['cases'])


def test_numerical_failure_row_stays_in_denominator(monkeypatch):
    oracle, runner = modules()
    grid = oracle.case_grid()[:2]
    real = runner.make_case

    def broken(config):
        if config == grid[0]:
            raise ArithmeticError('deliberate oracle failure')
        return real(config)

    monkeypatch.setattr(runner, 'make_case', broken)
    result = runner.run(grid=grid)
    assert result['planned'] == len(result['cases']) == 2
    assert result['evaluated'] == result['failed'] == 1
    assert result['cases'][0]['status'] == 'failed'
    assert result['study_gate'] == 'failed'


def test_publication_is_finite_exclusive_and_failure_exits_two(tmp_path):
    _, runner = modules()
    path = tmp_path/'evidence.json'
    assert runner.publish({'failed': 1}, path) == 2
    assert json.loads(path.read_text()) == {'failed': 1}
    with pytest.raises(FileExistsError):
        runner.publish({'failed': 0}, path)
    assert json.loads(path.read_text()) == {'failed': 1}
    nonfinite = tmp_path/'nan.json'
    with pytest.raises(ValueError):
        runner.publish({'failed': 0, 'bad': np.nan}, nonfinite)
    assert not nonfinite.exists()


@pytest.mark.parametrize('reason', ['omission', 'dirty_sources', 'incomplete_protocol'])
def test_failed_study_gate_is_nonzero_even_without_exception_rows(tmp_path, reason):
    _, runner = modules()
    result = dict(failed=0, study_gate='failed', within_cap_truth_omissions=int(reason == 'omission'),
                  sources_clean=reason != 'dirty_sources', protocol_complete=reason != 'incomplete_protocol')
    path = tmp_path/(reason+'.json')
    assert runner.publish(result, path) == 2
    assert json.loads(path.read_text()) == result


def test_successful_numerical_gate_exits_zero(tmp_path):
    _, runner = modules()
    assert runner.publish(dict(failed=0, study_gate='passed_conditional_numerical'), tmp_path/'pass.json') == 0
