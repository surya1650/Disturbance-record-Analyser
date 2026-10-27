import importlib
import json

import pytest


def api():
    return importlib.import_module('scripts.source_time_validation')


def test_frozen_grid_and_independent_rational_oracle():
    a = api()
    assert len(a.case_grid()) == 108
    out = a.run(grid=a.case_grid()[:3])
    assert out['evaluated'] == 3 and out['failed'] == 0
    assert all(r['max_time_error_s'] < 1e-12 for r in out['cases'])
    json.dumps(out, allow_nan=False)


def test_failure_retains_denominator(monkeypatch):
    a = api()
    def broken(config):
        raise ArithmeticError('injected failure')
    monkeypatch.setattr(a, 'evaluate', broken)
    out = a.run(grid=a.case_grid()[:2])
    assert out['planned'] == out['failed'] == len(out['cases']) == 2
    assert out['study_gate'] == 'failed'


def test_publication_is_exclusive_and_failure_nonzero(tmp_path):
    a = api()
    p = tmp_path/'evidence.json'
    assert a.publish(dict(study_gate='failed'), p) == 2
    with pytest.raises(FileExistsError):
        a.publish(dict(study_gate='passed_conditional_inspection'), p)
