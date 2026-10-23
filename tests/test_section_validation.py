"""The offline experiment must account for refusals and expose shared bias."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture(scope='module')
def experiment():
    return importlib.import_module('scripts.section_numerical_validation').run(seed=854)


def test_every_planned_case_is_accounted_for_and_ideal_chainage_is_independent(experiment):
    assert experiment['planned'] == 7056
    assert experiment['located']+experiment['refused'] == experiment['planned']
    for scenario in experiment['scenarios'].values():
        assert scenario['planned'] == 1008
        assert scenario['located']+scenario['refused'] == 1008
        assert sum(scenario['refusal_reasons'].values()) == scenario['refused']
    ideal = experiment['scenarios']['ideal']
    assert ideal['located'] == 1008 and ideal['refused'] == 0
    assert ideal['max_error_km'] < 1e-7
    assert all(group['max_error_km'] < 1e-7 for group in ideal['by_mode'].values())
    json.dumps(experiment, allow_nan=False)


def test_perturbations_expose_error_instead_of_reporting_only_a_small_residual(experiment):
    for name in ('noise_1pct', 'remote_current_plus10pct', 'first_section_z_plus20pct'):
        result = experiment['scenarios'][name]
        assert result['located'] > 0
        assert result['max_error_km'] > .01
    for name in ('remote_current_plus10pct', 'first_section_z_plus20pct', 'remote_polarity_reversed'):
        assert experiment['scenarios'][name]['descriptive_spread_contains_truth'] == 0
    assert experiment['scenarios']['noise_5pct']['refused'] > 0


def test_cli_refuses_to_overwrite_existing_evidence(tmp_path):
    path = tmp_path/'existing.json'
    path.write_text('original', encoding='utf-8')
    proc = subprocess.run([sys.executable, 'scripts/section_numerical_validation.py', '--output', str(path)],
                          env=dict(os.environ, PYTHONPATH='src;.'), capture_output=True, text=True)
    assert proc.returncode != 0
    assert path.read_text() == 'original'


def test_script_has_no_dependency_on_current_working_directory(tmp_path):
    # Existing output gives a cheap boundary check without paying for another sweep.
    script = Path(__file__).resolve().parents[1]/'scripts/section_numerical_validation.py'
    path = tmp_path/'existing.json'
    path.write_text('original')
    proc = subprocess.run([sys.executable, str(script), '--output', str(path)], cwd=tmp_path,
                          capture_output=True, text=True)
    assert proc.returncode != 0
    assert 'already exists' in proc.stderr
