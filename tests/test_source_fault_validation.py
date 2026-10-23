"""Refusal-aware accounting and controls for the wider independent envelope."""
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


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
