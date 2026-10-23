"""Independent branch-law checks and refusal-aware experiment accounting."""
import cmath
import json
import math

import pytest

from dranalyser.validation.sequence_envelope import run_envelope, sequence_case
from scripts.numerical_envelope import main


@pytest.mark.parametrize('m', [.05, .5, .95])
@pytest.mark.parametrize('ratio', [.1, 1, 1000])
@pytest.mark.parametrize('angle', [-math.pi, 0, 1.13])
def test_independent_sequence_case_obeys_source_and_line_ohm_laws(m, ratio, angle):
    row = sequence_case(m, ratio, angle)
    vs, is_, vr, ir = row['quantities']
    vr, ir = vr*cmath.exp(-1j*angle), ir*cmath.exp(-1j*angle)
    # Prescribed fault-node voltage; source EMFs are zero in negative sequence.
    assert vs + (4+12j)*is_ == pytest.approx(0, abs=1e-10)
    assert vr + ratio*(9+20j)*ir == pytest.approx(0, abs=1e-10)
    assert vs-m*(3+40j)*is_ == pytest.approx(100+40j, abs=1e-10)
    assert vr-(1-m)*(3+40j)*ir == pytest.approx(100+40j, abs=1e-10)


@pytest.mark.parametrize('bad', [0, -1, True, 1.5])
def test_envelope_rejects_invalid_repetition_count(bad):
    with pytest.raises(ValueError):
        run_envelope(repetitions=bad)


def test_envelope_is_seeded_finite_and_keeps_every_planned_refusal():
    first = run_envelope(seed=854, repetitions=1)
    assert first == run_envelope(seed=854, repetitions=1)
    assert first != run_envelope(seed=855, repetitions=1)
    json.dumps(first, allow_nan=False)
    cases, summary = first['cases'], first['summary']
    assert len({row['case_id'] for row in cases}) == len(cases)
    assert summary['planned'] == len(cases) > 0
    assert summary['located'] + summary['refused'] == len(cases)
    assert sum(g['planned'] for g in first['by_scenario'].values()) == len(cases)
    assert summary['refused'] > 0  # strong noise/infeed imbalance remains visible
    ideal = [r for r in cases if r['scenario'] == 'ideal']
    assert all(r['located'] and r['error_pct'] < 1e-7 for r in ideal)
    assert first['by_scenario']['ideal']['diagnostic_interval_contains_truth_fraction'] == 1
    biased = [r for r in cases if r['scenario'] == 'line_impedance_plus_20pct']
    assert any(r['located'] and r['error_pct'] > .5 for r in biased)
    assert summary['within_half_percent_all_planned_fraction'] == pytest.approx(
        sum(r['located'] and r['error_pct'] <= .5 for r in cases)/len(cases))


def test_command_refuses_to_overwrite_an_existing_sweep(tmp_path, capsys):
    path = tmp_path/'envelope.json'
    assert main(['--repetitions', '1', '--out', str(path)]) == 0
    original = path.read_bytes()
    report = json.loads(original)
    assert report['schema'] == 'dranalyser.numerical-envelope.v1'
    assert 'synthetic' in report['limits'].lower()
    with pytest.raises(FileExistsError):
        main(['--repetitions', '1', '--out', str(path)])
    assert path.read_bytes() == original
    assert capsys.readouterr().out
