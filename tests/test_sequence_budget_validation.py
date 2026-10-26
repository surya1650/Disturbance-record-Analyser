"""Bounded sample caps and their deliberately underclaimed counterexamples."""
import importlib
import json

import numpy as np
import pytest


def source():
    return importlib.import_module('tests.sequence_budget_records')


def runner():
    return importlib.import_module('scripts.sequence_budget_validation')


def test_metrology_adc_roundtrip_has_primary_units_and_known_caps(tmp_path):
    rec, ideal, caps, truth = source().records(tmp_path, split='development', i2=100, scenario='quantization')
    assert set(rec.analog) == set(('IA', 'IB', 'IC', 'VA', 'VB', 'VC'))
    assert rec.fs == 3500 and truth['true_frequency_hz'] == 48 and not rec.blocked()
    for name in ideal:
        meta = rec.analog_meta[name]
        half_step = .5*meta.a*meta.primary/meta.secondary
        assert meta.ps == 'S' and meta.normalised
        assert np.max(abs(rec.analog[name]-ideal[name])) <= half_step+1e-8
    assert all(caps[n] > 0 for n in ('IA', 'IB', 'IC'))


@pytest.mark.parametrize('scenario', ['quantization', 'uniform_small', 'uniform_large',
    'colored_small', 'colored_large', 'square_small', 'square_large', 'gain', 'polarity', 'alias'])
def test_sample_cap_truth_is_separate_from_the_budget_assumption(tmp_path, scenario):
    rec, ideal, caps, truth = source().records(tmp_path, split='validation', i2=100, scenario=scenario)
    within = all(np.max(abs(rec.analog[n]-ideal[n])) <= caps[n]+1e-8 for n in caps)
    assert within is (scenario not in ('gain', 'polarity', 'alias'))
    assert 'excludes' in truth['provenance']


def tiny_grid(module, monkeypatch):
    rows = [dict(split='development', i2=0, scenario='quantization'),
            dict(split='validation', i2=100, scenario='colored_small'),
            dict(split='validation', i2=100, scenario='gain'),
            dict(split='development', i2=.1, scenario='uniform_large')]
    monkeypatch.setattr(module, 'case_grid', lambda: rows)


def test_actual_dsp_matrix_keeps_assumption_masks_and_all_observations(monkeypatch):
    module = runner()
    tiny_grid(module, monkeypatch)
    out = module.run()
    assert out['planned_records'] == out['evaluated_records'] == 4 and out['failed_records'] == 0
    assert out['within_assumption_bound_misses'] == 0
    assert out['bounded_assumption_records'] == 3 and out['assumption_violating_records'] == 1
    assert out['conditional_pass_observations'] > 0 and out['withheld_observations'] > 0
    assert out['out_of_scope_radius_exceedances'] > 0
    assert out['evaluated_observations'] == out['conditional_pass_observations']+out['withheld_observations']
    assert out['validation_status'] == 'passed_conditional_study' and out['authorizes_location'] is False
    for group in ('split', 'scenario', 'i2'):
        assert sum(r['planned_records'] for r in out['by_'+group].values()) == 4
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('stage', ['records', 'evaluate', 'nonfinite'])
def test_failures_retain_planned_record_denominators(monkeypatch, stage):
    module = runner()
    tiny_grid(module, monkeypatch)
    def fail(*args, **kwargs):
        raise ArithmeticError('injected budget validation failure')
    if stage == 'nonfinite':
        original = module.evaluate
        def nonfinite(*args, **kwargs):
            result = original(*args, **kwargs)
            result['maximum_i2_error_primary_a'] = float('nan')
            return result
        monkeypatch.setattr(module, 'evaluate', nonfinite)
    else:
        monkeypatch.setattr(module, stage, fail)
    out = module.run()
    assert out['planned_records'] == out['failed_records'] == 4
    assert out['validation_status'] == 'failed' and len(out['cases']) == 4
    json.dumps(out, allow_nan=False)


def test_within_assumption_miss_fails_scientific_gate(monkeypatch):
    module = runner()
    tiny_grid(module, monkeypatch)
    original = module.evaluate
    def injected_miss(*args, **kwargs):
        result = original(*args, **kwargs)
        result['within_assumption_bound_misses'] += 1
        return result
    monkeypatch.setattr(module, 'evaluate', injected_miss)
    out = module.run()
    assert out['failed_records'] == 0 and out['within_assumption_bound_misses'] > 0
    assert out['validation_status'] == 'failed'


def test_existing_and_racing_publications_are_preserved(tmp_path, monkeypatch):
    module = runner()
    path = tmp_path/'exists.json'
    path.write_text('original')
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(path)])
    monkeypatch.setattr(module, 'run', lambda: pytest.fail('must not compute'))
    with pytest.raises(SystemExit):
        module.main()
    assert path.read_text() == 'original'
    race = tmp_path/'race.json'
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(race)])
    def concurrent():
        race.write_text('other evidence')
        return dict(validation_status='passed_conditional_study')
    monkeypatch.setattr(module, 'run', concurrent)
    with pytest.raises(SystemExit):
        module.main()
    assert race.read_text() == 'other evidence'


def test_failed_run_publishes_finite_json_and_exit2(tmp_path, monkeypatch):
    module = runner()
    path = tmp_path/'failed.json'
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(path)])
    monkeypatch.setattr(module, 'run', lambda: dict(validation_status='failed', failed_records=1))
    assert module.main() == 2
    assert json.loads(path.read_text())['failed_records'] == 1
