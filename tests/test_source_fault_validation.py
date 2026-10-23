"""Refusal-aware accounting and controls for the wider independent envelope."""
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
import numpy as np


@pytest.fixture(scope='module')
def experiment():
    return importlib.import_module('scripts.source_fault_validation').run()


def test_all_windows_and_balanced_controls_keep_their_denominators(experiment):
    assert experiment['planned'] == 19008
    assert experiment['located']+experiment['refused'] == 19008
    for scenario in experiment['scenarios'].values():
        assert scenario['planned'] == 6336
        assert scenario['unbalanced']['planned'] == 5184
        assert scenario['balanced_controls']['planned'] == 1152
        assert scenario['screened_unbalanced']['planned'] == 5184
        for key in ('by_profile', 'by_fault', 'by_reference', 'by_infeed_ratio', 'by_source_fault'):
            assert sum(g['planned'] for g in scenario[key].values()) == 6336
        assert sum(scenario['refusal_reasons'].values()) == scenario['refused']
    json.dumps(experiment, allow_nan=False)


def test_ideal_accepted_unbalanced_locations_agree_with_independent_physical_truth(experiment):
    ideal = experiment['scenarios']['ideal']
    assert ideal['unbalanced']['located'] > 1000
    assert ideal['unbalanced']['max_error_km'] < 1e-6
    for name in ('AG', 'BG', 'CG', 'AB', 'BC', 'CA', 'ABG', 'BCG', 'CAG'):
        assert ideal['by_fault'][name]['located'] > 0
        assert ideal['by_fault'][name]['max_error_km'] < 1e-6
    for profile in ideal['by_profile'].values():
        assert profile['unbalanced']['planned'] == 648
        assert profile['unbalanced']['max_error_km'] < 1e-6
        assert profile['balanced_controls']['planned'] == 144


def test_weak_source_and_noisy_outcomes_are_not_filtered_by_error(experiment):
    noisy = experiment['scenarios']['noise_1pct']
    assert noisy['unbalanced']['max_error_km'] > .01
    assert noisy['refused'] > 0
    assert noisy['by_profile']['weak_R_10000']['planned'] == 792
    assert noisy['by_profile']['weak_S_10000']['planned'] == 792
    assert noisy['screened_unbalanced']['located'] <= noisy['unbalanced']['located']
    assert experiment['max_oracle_kcl_residual_a'] < 1e-6


@pytest.mark.parametrize('negative,expected', [([0, 0, 0, 0], [1, .1, 1, .1]),
                                              ([20, 2, 10, .5], [20, 2, 20, 2])])
def test_noise_scale_stays_nonzero_without_negative_sequence_and_tracks_stronger_terminal(negative, expected):
    runner = importlib.import_module('scripts.source_fault_validation')
    assert runner.measurement_scales(negative, 100, [10, 5]) == pytest.approx(expected)


def test_cli_cannot_overwrite_existing_evidence_from_another_directory(tmp_path):
    path = tmp_path/'evidence.json'
    path.write_text('original')
    script = Path(__file__).resolve().parents[1]/'scripts/source_fault_validation.py'
    proc = subprocess.run([sys.executable, str(script), '--output', str(path)], cwd=tmp_path,
                          capture_output=True, text=True)
    assert proc.returncode != 0 and 'already exists' in proc.stderr
    assert path.read_text() == 'original'


@pytest.mark.parametrize('error', [ArithmeticError('injected KCL failure'), np.linalg.LinAlgError('injected singular network')])
def test_failed_oracle_windows_remain_in_every_denominator_and_fail_the_run(monkeypatch, error):
    runner = importlib.import_module('scripts.source_fault_validation')
    def broken(*args, **kwargs):
        raise error
    monkeypatch.setattr(runner, 'solve', broken)
    result = runner.run()
    assert result['completion_status'] == 'oracle_failure'
    assert result['oracle_failures'] == 2112
    assert result['oracle_failed_windows'] == result['refused'] == result['planned'] == 19008
    assert result['located'] == 0 and result['max_error_km'] is None
    assert result['max_oracle_kcl_residual_a'] is None
    assert result['oracle_failure_witnesses'] and result['oracle_failure_witnesses'][0]['error_type'] == type(error).__name__
    for group in result['scenarios'].values():
        assert group['oracle_failed_windows'] == group['planned'] == 6336
        assert sum(group['refusal_reasons'].values()) == 6336
        for field in ('by_profile', 'by_fault', 'by_reference', 'by_infeed_ratio', 'by_source_fault'):
            assert sum(g['oracle_failed_windows'] for g in group[field].values()) == 6336
        assert group['screened_unbalanced']['oracle_failed_windows'] == 5184
        assert all('Oracle failure' in reason for reason in group['screened_unbalanced']['refusal_reasons'])
    json.dumps(result, allow_nan=False)


def test_cli_publishes_failed_oracle_evidence_and_returns_failure(tmp_path, monkeypatch):
    runner = importlib.import_module('scripts.source_fault_validation')
    path = tmp_path/'failed.json'
    def broken(*args, **kwargs):
        raise ArithmeticError('injected KCL failure')
    monkeypatch.setattr(runner, 'solve', broken)
    monkeypatch.setattr(sys, 'argv', ['source_fault_validation.py', '--output', str(path)])
    assert runner.main() == 2
    result = json.loads(path.read_text())
    assert result['completion_status'] == 'oracle_failure' and result['planned'] == 19008
    assert result['guarded_actual_dsp']['status'] == 'not_run'


def test_configuration_errors_remain_explicit_and_leave_no_output(tmp_path, monkeypatch):
    runner = importlib.import_module('scripts.source_fault_validation')
    path = tmp_path/'invalid.json'
    def invalid(*args, **kwargs):
        raise ValueError('invalid network definition')
    monkeypatch.setattr(runner, 'solve', invalid)
    monkeypatch.setattr(sys, 'argv', ['source_fault_validation.py', '--output', str(path)])
    with pytest.raises(ValueError, match='invalid network definition'):
        runner.main()
    assert not path.exists()


def test_one_failed_network_preserves_surviving_seeded_numerical_outcomes(monkeypatch):
    runner = importlib.import_module('scripts.source_fault_validation')
    monkeypatch.setattr(runner, 'PROFILES', ('baseline',))
    monkeypatch.setattr(runner, 'FAULTS', ('AG',))
    monkeypatch.setattr(runner, 'GEOMETRIES', [runner.GEOMETRIES[0]])
    original_solve, original_window, outcomes = runner.solve, runner.section_window, []
    def observed(*args, **kwargs):
        result = original_window(*args, **kwargs)
        outcomes.append(result)
        return result
    monkeypatch.setattr(runner, 'section_window', observed)
    runner.run()
    surviving = outcomes[9:]  # one physical network has 3 references x 3 noise windows
    outcomes.clear()
    calls = 0
    def once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ArithmeticError('one failed physical network')
        return original_solve(*args, **kwargs)
    monkeypatch.setattr(runner, 'solve', once)
    result = runner.run()
    assert result['planned'] == 108 and result['oracle_failures'] == 1
    assert result['oracle_failed_windows'] == 9
    assert all(g['planned'] == 36 and g['oracle_failed_windows'] == 3 for g in result['scenarios'].values())
    # A failed network must not shift the noise realizations or the real solver
    # answers for unrelated surviving networks.
    assert outcomes == surviving
