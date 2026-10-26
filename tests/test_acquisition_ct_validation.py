"""Frozen candidate is diagnostic only; no production gate mutation."""
import json

import numpy as np
import pytest

from scripts.acquisition_quality_candidate import assess
from scripts import acquisition_ct_validation as runner


def wave(fs=2400, f=50):
    t = np.arange(round(.3*fs))/fs
    return t, np.sqrt(2)*np.sin(2*np.pi*f*t+.3)


@pytest.mark.parametrize('noise', [0, .001, .01])
def test_bounded_white_noise_is_not_coherent_distortion(noise):
    t, u = wave()
    result = assess(u+noise*np.random.default_rng(12).normal(size=len(t)), 2400, 50)
    assert result['status'] == 'candidate_pass'
    assert result['authorizes_location'] is False
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('kind', ['harmonic', 'clip', 'dropout', 'noise'])
def test_nonct_distortion_and_large_noise_do_not_pass(kind):
    t, u = wave()
    if kind == 'harmonic':
        u += .15*np.sin(2*np.pi*150*t)
    elif kind == 'clip':
        u = np.clip(u, -.6, .6)
    elif kind == 'dropout':
        u[300:312] = 0
    else:
        u += .1*np.random.default_rng(8).normal(size=len(u))
    assert assess(u, 2400, 50)['status'] != 'candidate_pass'


@pytest.mark.parametrize('u,fs,f', [(np.zeros(720),2400,50), (np.ones(720),2400,50),
    ([1,np.nan],2400,50), (np.ones(8),2400,50), (np.ones(720),0,50),
    (np.ones(720),2400,np.inf), (np.ones(720),500,50)])
def test_unsupported_and_weak_inputs_withheld(u, fs, f):
    result = assess(u, fs, f)
    assert result['status'] == 'unsupported'
    assert result['authorizes_location'] is False
    json.dumps(result, allow_nan=False)


def test_small_run_retains_ct_truth_controls_and_strata(monkeypatch):
    monkeypatch.setattr(runner, 'ct_grid', lambda split: [(50, 2400, .31, 1.4, .065, 1.6, .4)])
    result = runner.run()
    assert result['planned'] == len(result['cases']) == 22
    assert result['failed'] == 0
    assert result['production_gates_changed'] is False
    assert result['splits']['development']['planned'] == result['splits']['holdout']['planned'] == 11
    ct = [r for r in result['cases'] if r['kind'] == 'ct']
    assert all('fundamental_error' in r and 'crossed_knee' in r for r in ct)
    assert all(r['candidate']['authorizes_location'] is False for r in result['cases'])
    json.dumps(result, allow_nan=False)


def test_failure_keeps_denominator_and_prevents_adoption(monkeypatch):
    monkeypatch.setattr(runner, 'ct_grid', lambda split: [(50, 2400, .31, 1.4, .065, 1.6, .4)])
    def fail(*args, **kwargs):
        raise ArithmeticError('injected CT integration failure')
    monkeypatch.setattr(runner, 'simulate', fail)
    result = runner.run()
    assert result['planned'] == 22 and result['failed'] == 4
    assert result['adoption_gate'] == 'failed'
    assert sum(r['status'] == 'failed' for r in result['cases']) == 4
    json.dumps(result, allow_nan=False)


def test_publication_does_not_overwrite(tmp_path, monkeypatch):
    path = tmp_path/'exists.json'
    path.write_text('original')
    monkeypatch.setattr('sys.argv', ['runner', '--output', str(path)])
    with pytest.raises(SystemExit):
        runner.main()
    assert path.read_text() == 'original'
