"""Full-record quality is research evidence, never an eligibility override."""
import importlib
import json

import numpy as np
import pytest

from tests.full_record_acquisition import records


def quality():
    return importlib.import_module('scripts.full_record_quality')


def runner():
    return importlib.import_module('scripts.full_record_validation')


def test_all_six_channels_have_explicit_secondary_units_and_no_authority(tmp_path):
    pair, truth = records(tmp_path, split='development', profile='baseline', fault='AG', scenario='clean')
    for end, rec in pair.items():
        out = quality().record_quality(rec, 49, truth[end]['window_indices'])
        assert out['status'] == 'candidate_pass'
        assert out['authorizes_location'] is False
        assert len(out['channels']) == 6
        assert out['channels']['IA']['unit'] == 'secondary_A'
        assert out['channels']['VA']['unit'] == 'secondary_V'
        json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('scenario', ['clip_i', 'clip_v', 'short', 'gap'])
def test_acquisition_and_window_refusals_survive_candidate(tmp_path, scenario):
    pair, truth = records(tmp_path, split='development', profile='baseline', fault='AG', scenario=scenario)
    values = [quality().record_quality(rec, 49, truth[end]['window_indices']) for end, rec in pair.items()]
    assert any(v['status'] != 'candidate_pass' for v in values)
    assert all(v['authorizes_location'] is False for v in values)


@pytest.mark.parametrize('defect', ['missing', 'nonfinite', 'weak', 'bad_ratio', 'bad_grid', 'voltage_harmonic'])
def test_missing_weak_and_defective_voltage_inputs_do_not_pass(tmp_path, defect):
    pair, truth = records(tmp_path, split='development', profile='baseline', fault='AG', scenario='clean')
    rec = pair['S']
    if defect == 'missing':
        del rec.analog['IC']
    elif defect == 'nonfinite':
        rec.analog['VA'][300] = np.nan
    elif defect == 'weak':
        rec.analog['IA'][:] = 1e-5+1e-10*np.sin(2*np.pi*49*rec.t)
    elif defect == 'bad_ratio':
        rec.analog_meta['VA'].secondary = 0
    elif defect == 'bad_grid':
        rec.t[300:] += .01
    else:
        rec.analog['VA'] += .15*np.max(abs(rec.analog['VA']))*np.sin(6*np.pi*49*rec.t)
    assert quality().record_quality(rec, 49, truth['S']['window_indices'])['status'] != 'candidate_pass'


@pytest.mark.parametrize('scenario', ['gain_i', 'gain_v', 'polarity'])
def test_coherent_gain_and_polarity_pass_shape_but_fail_independent_truth(tmp_path, scenario):
    pair, truth = records(tmp_path, split='development', profile='baseline', fault='AG', scenario=scenario)
    end = 'R' if scenario == 'polarity' else 'S'
    assert quality().record_quality(pair[end], 49, truth[end]['window_indices'])['status'] == 'candidate_pass'
    errors = quality().truth_errors(pair, truth)
    assert errors['harmful_measurement'] is True
    assert max(errors['maximum_current_error'], errors['maximum_voltage_error']) > .05


def test_balanced_negative_sequence_uses_explicit_finite_floor(tmp_path):
    pair, truth = records(tmp_path, split='development', profile='baseline', fault='ABC', scenario='clean')
    out = quality().truth_errors(pair, truth)
    assert all(v['i2_denominator_secondary_a'] >= 1e-6 for v in out['terminals'].values())
    json.dumps(out, allow_nan=False)


def small_grid(module, monkeypatch):
    rows = [dict(split='development', profile='baseline', fault='AG', scenario='clean'),
            dict(split='validation', profile='baseline', fault='ABC', scenario='gain_i')]
    monkeypatch.setattr(module, 'case_grid', lambda: rows)
    return rows


def test_small_grid_exercises_actual_workflows_and_keeps_every_stratum(monkeypatch):
    module = runner()
    small_grid(module, monkeypatch)
    out = module.run()
    assert out['incidents'] == out['evaluated_incidents'] == 2
    assert out['planned'] == 4 and out['failed'] == 0
    assert out['located']+out['refused'] == 4
    assert out['production_gates_changed'] is False and out['adoption_gate'] == 'failed'
    assert all(len(row['workflows']) == 2 and len(row['quality']) == 2 for row in out['cases'])
    for key in ('split', 'profile', 'fault', 'scenario'):
        assert sum(r['planned'] for r in out['by_'+key].values()) == 4
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('where', ['records', 'evaluate', 'nonfinite'])
def test_per_case_failure_keeps_both_workflows_and_blocks_adoption(monkeypatch, where):
    module = runner()
    small_grid(module, monkeypatch)
    def fail(*args, **kwargs):
        raise ArithmeticError('injected full-record failure')
    if where == 'nonfinite':
        original = module.evaluate
        def nonfinite(*args, **kwargs):
            out = original(*args, **kwargs)
            out['frequency_hz']['S'] = float('nan')
            return out
        monkeypatch.setattr(module, 'evaluate', nonfinite)
    else:
        monkeypatch.setattr(module, where, fail)
    out = module.run()
    assert out['incidents'] == 2 and out['planned'] == out['failed'] == 4
    assert out['adoption_gate'] == 'failed'
    assert all(row['status'] == 'failed' and len(row['workflows']) == 2 for row in out['cases'])
    json.dumps(out, allow_nan=False)


def test_existing_output_rejected_before_computation(tmp_path, monkeypatch):
    module = runner()
    path = tmp_path/'existing.json'
    path.write_text('original')
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(path)])
    monkeypatch.setattr(module, 'run', lambda: pytest.fail('must not compute'))
    with pytest.raises(SystemExit):
        module.main()
    assert path.read_text() == 'original'


def test_racing_output_preserved_and_failed_run_has_exit2(tmp_path, monkeypatch):
    module = runner()
    path = tmp_path/'failed.json'
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(path)])
    monkeypatch.setattr(module, 'run', lambda: dict(failed=2))
    assert module.main() == 2
    assert json.loads(path.read_text())['failed'] == 2
    race = tmp_path/'race.json'
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(race)])
    def concurrent():
        race.write_text('other evidence')
        return dict(failed=0)
    monkeypatch.setattr(module, 'run', concurrent)
    with pytest.raises(SystemExit):
        module.main()
    assert race.read_text() == 'other evidence'


def test_known_harmful_development_pass_blocks_adoption(monkeypatch):
    module = runner()
    monkeypatch.setattr(module, 'case_grid', lambda: [
        dict(split='development', profile='baseline', fault='ABC', scenario='gain_i'),
        dict(split='validation', profile='baseline', fault='AG', scenario='ct_multi')])
    out = module.run()
    assert out['failed'] == out['located'] == 0
    assert out['harmful_quality_pass'] == 1
    assert out['by_split']['validation']['harmful_quality_pass'] == 0
    assert out['by_split']['validation']['harmful_ct_incidents'] == 1
    assert out['adoption_gate'] == 'failed'
