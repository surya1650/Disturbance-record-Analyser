"""Small real-DSP sweep plus complete failure/publication accounting."""
import importlib
import json
import sys

import pytest


@pytest.fixture
def runner(monkeypatch):
    module = importlib.import_module('scripts.noisy_dsp_validation')
    monkeypatch.setattr(module, 'PROFILES', ('baseline',))
    monkeypatch.setattr(module, 'FAULTS', ('AG', 'ABC'))
    monkeypatch.setattr(module, 'NOISE', (0, .001))
    monkeypatch.setattr(module, 'TIMING', ('declared', 'gap'))
    return module


def test_small_actual_sweep_retains_all_workflows_controls_and_strata(runner):
    out = runner.run()
    assert out['incidents'] == 8 and out['planned'] == 16
    assert out['completion_status'] == 'complete' and out['failed'] == 0
    assert out['located']+out['refused']+out['failed'] == out['planned']
    for name in ('by_workflow', 'by_noise', 'by_timing', 'by_profile', 'by_fault'):
        assert sum(r['planned'] for r in out[name].values()) == 16
        assert all(r['unbalanced']['planned']+r['balanced_controls']['planned'] == r['planned'] for r in out[name].values())
    assert out['unbalanced']['planned'] == out['balanced_controls']['planned'] == 8
    assert out['balanced_controls']['located'] == 0
    assert all(r['status'] == 'withheld' for r in out['cases'] if r['timing'] == 'gap')
    json.dumps(out, allow_nan=False)


def test_numerical_exception_retains_all_planned_outcomes(runner, monkeypatch):
    def fail(*args, **kwargs):
        raise ArithmeticError('injected DSP numerical failure')
    monkeypatch.setattr(runner, 'evaluate', fail)
    out = runner.run()
    assert out['planned'] == out['failed'] == 16
    assert out['completion_status'] == 'failed'
    assert all(r['error_type'] == 'ArithmeticError' for r in out['cases'])
    for name in ('by_workflow', 'by_noise', 'by_timing', 'by_profile', 'by_fault'):
        assert sum(r['failed'] for r in out[name].values()) == 16


def test_existing_output_refused_before_work(runner, tmp_path, monkeypatch):
    output = tmp_path/'existing.json'
    output.write_text('original')
    monkeypatch.setattr(sys, 'argv', ['runner', '--output', str(output)])
    def unexpected(*args, **kwargs):
        pytest.fail('Computation must not start for an existing evidence file')
    monkeypatch.setattr(runner, 'run', unexpected)
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2 and output.read_text() == 'original'


def test_failed_run_publishes_valid_json_exit2(runner, tmp_path, monkeypatch):
    output = tmp_path/'failed.json'
    def fail(*args, **kwargs):
        raise ArithmeticError('injected oracle failure')
    monkeypatch.setattr(runner, 'records', fail)
    monkeypatch.setattr(sys, 'argv', ['runner', '--output', str(output)])
    assert runner.main() == 2
    assert json.loads(output.read_text())['failed'] == 16


def test_configuration_failure_creates_no_empty_output(runner, tmp_path, monkeypatch):
    output = tmp_path/'invalid.json'
    def fail(*args, **kwargs):
        raise ValueError('invalid model configuration')
    monkeypatch.setattr(runner, 'records', fail)
    monkeypatch.setattr(sys, 'argv', ['runner', '--output', str(output)])
    with pytest.raises(ValueError, match='invalid model'):
        runner.main()
    assert not output.exists()


def test_exclusive_publication_keeps_concurrent_writers_evidence(runner, tmp_path, monkeypatch):
    output = tmp_path/'race.json'
    def concurrent(*args, **kwargs):
        output.write_text('concurrent evidence')
        return dict(planned=0, located=0, refused=0, failed=0)
    monkeypatch.setattr(runner, 'run', concurrent)
    monkeypatch.setattr(sys, 'argv', ['runner', '--output', str(output)])
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2 and output.read_text() == 'concurrent evidence'
