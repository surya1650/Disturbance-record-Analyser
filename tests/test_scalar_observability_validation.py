"""Parsed independent source/CT matrix and honest candidate adoption accounting."""
import importlib
import json

import numpy as np
import pytest


def source():
    return importlib.import_module('tests.scalar_observability_records')


def runner():
    return importlib.import_module('scripts.scalar_observability_validation')


def test_new_uniform_network_records_roundtrip_integer_adc_without_mutating_old_grid(tmp_path):
    old = importlib.import_module('tests.full_record_signals')
    snapshot = repr((old.SECTIONS, old.SPLITS))
    pair, truth = source().records(tmp_path, split='development', profile='baseline', fault='AG', scenario='clean')
    assert pair['S'].fs == 3000 and pair['R'].fs == 1800
    for end, rec in pair.items():
        assert not rec.blocked() and set(rec.analog) == {'IA', 'IB', 'IC', 'VA', 'VB', 'VC'}
        for name, actual in rec.analog.items():
            meta = rec.analog_meta[name]
            expected = truth[end]['samples'][name]*meta.primary/meta.secondary
            assert np.max(abs(actual-expected)) <= .5*meta.a*meta.primary/meta.secondary+1e-8
    assert repr((old.SECTIONS, old.SPLITS)) == snapshot


@pytest.mark.parametrize('scenario', ['ct_all', 'gain_i', 'polarity', 'alias'])
def test_corruption_truth_is_computed_separately_from_candidate_inputs(tmp_path, scenario):
    from scripts.full_record_quality import truth_errors
    pair, truth = source().records(tmp_path, split='validation', profile='baseline', fault='AG', scenario=scenario)
    errors = truth_errors(pair, truth)
    assert errors['harmful_measurement'] is True
    if scenario == 'ct_all':
        assert errors['maximum_ct_current_error'] > .05
    assert all('truth' not in rec.notes for rec in pair.values())


def tiny(module, monkeypatch):
    monkeypatch.setattr(module, 'case_grid', lambda: [
        dict(split='development', profile='baseline', fault='AG', scenario='clean'),
        dict(split='validation', profile='baseline', fault='BC', scenario='gain_i'),
        dict(split='validation', profile='baseline', fault='ABC', scenario='ct_all')])


def test_actual_scalar_matrix_retains_observations_and_only_suppresses_locations(monkeypatch):
    module = runner()
    tiny(module, monkeypatch)
    out = module.run()
    assert out['planned_incidents'] == out['evaluated_incidents'] == 3 and out['failed_incidents'] == 0
    assert out['candidate_pass']+out['candidate_withheld'] == 3
    assert out['overlay_located'] <= out['baseline_located']
    assert out['authorizes_location'] is False and out['production_consumers_changed'] is False
    assert out['adoption_gate'] == 'failed', 'Incomplete grid cannot become adoption evidence.'
    for row in out['cases']:
        if row['overlay']['status'] == 'located':
            assert row['candidate']['status'] == 'candidate_pass'
            assert row['overlay']['reported_km'] == row['baseline']['reported_km']
        assert row['clock_alignment_eligible'] is False
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('stage', ['records', 'evaluate', 'nonfinite'])
def test_failures_keep_all_planned_incident_rows(monkeypatch, stage):
    module = runner()
    tiny(module, monkeypatch)
    original = module.evaluate
    def fail(*args, **kwargs):
        if stage == 'nonfinite':
            row = original(*args, **kwargs)
            row['truth']['maximum_current_error'] = float('nan')
            return row
        raise ArithmeticError('injected independent matrix failure')
    monkeypatch.setattr(module, 'evaluate' if stage == 'nonfinite' else stage, fail)
    out = module.run()
    assert out['failed_incidents'] == out['planned_incidents'] == len(out['cases']) == 3
    assert out['adoption_gate'] == 'failed'
    json.dumps(out, allow_nan=False)


def test_harmful_pass_remains_a_failed_adoption_reason(monkeypatch):
    module = runner()
    tiny(module, monkeypatch)
    original = module.evaluate
    def harmful(*args, **kwargs):
        row = original(*args, **kwargs)
        row['candidate']['status'] = 'candidate_pass'
        row['truth']['harmful_measurement'] = True
        return row
    monkeypatch.setattr(module, 'evaluate', harmful)
    out = module.run()
    assert out['harmful_candidate_pass'] == 3
    assert any('harmful' in s.lower() for s in out['adoption_failure_reasons'])


def test_empty_and_invalid_grids_refuse_before_execution(monkeypatch):
    module = runner()
    for grid in ([], [dict(split='development', profile='baseline', fault='XX', scenario='clean')]):
        monkeypatch.setattr(module, 'case_grid', lambda grid=grid: grid)
        with pytest.raises(ValueError):
            module.run()


def test_existing_racing_and_nonfinite_publications_preserve_prior_evidence(tmp_path, monkeypatch):
    module = runner()
    path = tmp_path/'existing.json'
    path.write_text('original')
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(path)])
    monkeypatch.setattr(module, 'run', lambda: pytest.fail('must not compute'))
    with pytest.raises(SystemExit):
        module.main()
    assert path.read_text() == 'original'
    race = tmp_path/'race.json'
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(race)])
    def concurrent():
        race.write_text('other')
        return dict(failed_incidents=0)
    monkeypatch.setattr(module, 'run', concurrent)
    with pytest.raises(SystemExit):
        module.main()
    assert race.read_text() == 'other'
    bad = tmp_path/'bad.json'
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(bad)])
    monkeypatch.setattr(module, 'run', lambda: dict(failed_incidents=0, value=float('inf')))
    with pytest.raises(ValueError):
        module.main()
    assert not bad.exists()


def test_numerical_failure_publishes_finite_json_and_returns_exit2(tmp_path, monkeypatch):
    module = runner()
    path = tmp_path/'failed.json'
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(path)])
    monkeypatch.setattr(module, 'run', lambda: dict(failed_incidents=1))
    assert module.main() == 2
    assert json.loads(path.read_text())['failed_incidents'] == 1
