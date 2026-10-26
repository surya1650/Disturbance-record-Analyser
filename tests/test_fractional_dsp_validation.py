"""New parsed-grid validation must retain physical and additive failures."""
import importlib
import json

import pytest


def runner():
    return importlib.import_module('scripts.fractional_dsp_validation')


def tiny(module, monkeypatch):
    monkeypatch.setattr(module, 'case_grid', lambda: [
        dict(split='development', i2=10, scenario='quantization'),
        dict(split='validation', i2=100, scenario='gain')])


def test_new_grid_uses_real_parser_without_mutating_historical_generator(monkeypatch):
    module = runner()
    original = importlib.import_module('tests.sequence_budget_records').SPLITS.copy()
    tiny(module, monkeypatch)
    out = module.run()
    assert out['evaluated_records'] == 2 and out['failed_records'] == 0
    assert out['bounded_assumption_records'] == out['assumption_violating_records'] == 1
    assert out['within_assumption_bound_misses'] == 0
    assert out['maximum_matched_kernel_physical_bias_primary_a'] < .01
    assert [r['fs'] for r in out['cases']] == [3200, 4100]
    assert out['out_of_scope_radius_exceedances'] > 0
    assert out['validation_status'] == 'passed_subset_study'
    assert not out['complete_grid_gate'] and not out['authorizes_location']
    assert importlib.import_module('tests.sequence_budget_records').SPLITS == original
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('failure', ['exception', 'nonfinite', 'bound_miss', 'physical_bias'])
def test_failed_evaluation_and_scientific_gates_retain_denominators(monkeypatch, failure):
    module = runner()
    tiny(module, monkeypatch)
    original = module.evaluate
    def injected(*args):
        if failure == 'exception':
            raise ArithmeticError('injected')
        row = original(*args)
        if failure == 'nonfinite':
            row['maximum_i2_error_primary_a'] = float('inf')
        elif failure == 'bound_miss':
            row['within_assumption_bound_misses'] = 1
        else:
            row['maximum_matched_kernel_physical_bias_primary_a'] = .011
        return row
    monkeypatch.setattr(module, 'evaluate', injected)
    out = module.run()
    assert out['planned_records'] == len(out['cases']) == 2
    assert out['validation_status'] == 'failed'
    assert out['failed_records'] == (2 if failure in ('exception', 'nonfinite') else 0)
    json.dumps(out, allow_nan=False)


def test_historical_replay_has_distinct_protocol_and_original_rates(monkeypatch):
    module = runner()
    tiny(module, monkeypatch)
    out = module.run(historical=True)
    assert out['protocol']['grid'] == 'historical_replay'
    assert [r['fs'] for r in out['cases']] == [3500, 2600]
    assert out['maximum_matched_kernel_physical_bias_primary_a'] < .01


def test_empty_or_invalid_configuration_refuses(monkeypatch):
    module = runner()
    for grid in ([], [dict(split='unknown', i2=10, scenario='gain')]):
        monkeypatch.setattr(module, 'case_grid', lambda grid=grid: grid)
        with pytest.raises(ValueError):
            module.run()


def test_existing_racing_and_nonfinite_publications_preserve_evidence(tmp_path, monkeypatch):
    module = runner()
    path = tmp_path/'evidence.json'
    path.write_text('original')
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(path)])
    monkeypatch.setattr(module, 'run', lambda **kwargs: pytest.fail('must not run'))
    with pytest.raises(SystemExit):
        module.main()
    assert path.read_text() == 'original'
    race = tmp_path/'race.json'
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(race)])
    def concurrent(**kwargs):
        race.write_text('other evidence')
        return dict(validation_status='passed_subset_study')
    monkeypatch.setattr(module, 'run', concurrent)
    with pytest.raises(SystemExit):
        module.main()
    assert race.read_text() == 'other evidence'
    bad = tmp_path/'bad.json'
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(bad)])
    monkeypatch.setattr(module, 'run', lambda **kwargs: dict(value=float('nan')))
    with pytest.raises(ValueError):
        module.main()
    assert not bad.exists()


def test_failure_publishes_finite_json_and_returns_exit2(tmp_path, monkeypatch):
    module = runner()
    path = tmp_path/'failed.json'
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(path)])
    monkeypatch.setattr(module, 'run', lambda **kwargs: dict(validation_status='failed', failed_records=2))
    assert module.main() == 2
    assert json.loads(path.read_text())['failed_records'] == 2
