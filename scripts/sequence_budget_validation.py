"""New bounded metrology matrix; conditional additive bounds never authorize location."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'src'))

from dranalyser.dsp.core import sliding_dft  # noqa: E402
from dranalyser.dsp.pipeline import analyse  # noqa: E402
from dranalyser.dsp.sequence_budget import dft_noise_radius, i2_budget  # noqa: E402
from tests.sequence_budget_records import I2_VALUES, SCENARIOS, SPLITS, records, validate  # noqa: E402

ABSOLUTE_TOLERANCE_A = 1e-8
RELATIVE_TOLERANCE = 1e-8


def case_grid():
    return [dict(split=split, i2=i2, scenario=scenario)
            for split, i2, scenario in itertools.product(SPLITS, I2_VALUES, SCENARIOS)]


def evaluate(rec, ideal, caps, truth):
    if rec.blocked():
        raise ValueError('Unexpected blocked metrology acquisition.')
    an = analyse(rec)
    ids = an.ps.window_indices(*truth['window_s'])
    if not len(ids):
        raise ArithmeticError('No complete metrology DSP supports.')
    names = ('IA', 'IB', 'IC')
    radii = [dft_noise_radius(rec.fs, an.freq, caps[n], tau=an.tau,
        uniform_grid=bool(np.allclose(np.diff(rec.t), 1/rec.fs, rtol=0, atol=1e-12))) for n in names]
    if any(r['status'] != 'conditional_bound' or r['n_window'] != an.ps.n_window for r in radii):
        raise ArithmeticError('Unsupported or mismatched actual DSP kernel.')
    phase_radii = [r['radius_primary_a'] for r in radii]
    reference = np.array([sliding_dft(ideal[n], rec.t, rec.fs, an.freq, tau=an.tau)[ids] for n in names])
    observed = np.array([an.ps.phasors[n][ids] for n in names])
    a = np.exp(2j*np.pi/3)
    expected_i2 = (reference[0]+a*a*reference[1]+a*reference[2])/3
    actual_i2 = an.ps.phasors['I2'][ids]
    if not np.all(np.isfinite([*reference, *observed, expected_i2, actual_i2])):
        raise ArithmeticError('Nonfinite metrology phasor.')
    assumptions = all(np.max(abs(rec.analog[n]-ideal[n])) <= caps[n]+ABSOLUTE_TOLERANCE_A for n in names)
    counts = dict(evaluated_observations=len(ids), conditional_pass_observations=0, withheld_observations=0,
                  within_assumption_bound_misses=0, out_of_scope_radius_exceedances=0,
                  conditional_physical_error_above_5pct=0)
    max_error, max_ratio, max_model_bias, worst = 0., -1., 0., None
    for offset, index in enumerate(ids):
        out = i2_budget(observed[:, offset], phase_radii, provenance=truth['provenance'])
        if out['status'] not in ('bounded_under_assumptions', 'withheld'):
            raise ArithmeticError('Unexpected unsupported valid sequence-budget inputs.')
        accepted = out['status'] == 'bounded_under_assumptions'
        counts['conditional_pass_observations' if accepted else 'withheld_observations'] += 1
        error = float(abs(actual_i2[offset]-expected_i2[offset]))
        radius = out['i2_radius_primary_a']
        ratio = error/radius
        relative = error/abs(expected_i2[offset]) if abs(expected_i2[offset]) > 1e-6 else None
        miss = bool(np.any(abs(observed[:, offset]-reference[:, offset]) > np.array(phase_radii)+ABSOLUTE_TOLERANCE_A) or
                    error > radius+ABSOLUTE_TOLERANCE_A or
                    accepted and (relative is None or relative > out['relative_error_bound']+RELATIVE_TOLERANCE))
        if assumptions:
            counts['within_assumption_bound_misses'] += miss
        elif error > radius+ABSOLUTE_TOLERANCE_A:
            counts['out_of_scope_radius_exceedances'] += 1
        physical = truth['physical_i2_rms_primary_a']*np.exp(1j*(truth['negative_phase_rad']-
            2*np.pi*truth['true_frequency_hz']*truth['pre']+
            2*np.pi*(truth['true_frequency_hz']-an.freq)*rec.t[index]))
        max_model_bias = max(max_model_bias, float(abs(expected_i2[offset]-physical)))
        if accepted and abs(physical) > 1e-6 and abs(actual_i2[offset]-physical)/abs(physical) > .05:
            counts['conditional_physical_error_above_5pct'] += 1
        max_error = max(max_error, error)
        if ratio > max_ratio:
            max_ratio = ratio
            worst = dict(sample_index=int(index), i2_error_primary_a=error, radius_primary_a=radius,
                matched_reference_i2_primary_a=float(abs(expected_i2[offset])), observed_relative_error=relative,
                status=out['status'], relative_error_bound=out['relative_error_bound'])
    return dict(status='evaluated', **counts, assumptions_satisfied=assumptions,
        maximum_i2_error_primary_a=max_error, maximum_error_over_radius=max_ratio,
        maximum_matched_kernel_physical_bias_primary_a=max_model_bias, worst_observation=worst,
        record_hash=rec.content_hash, tracked_frequency_hz=an.freq, fs=rec.fs, n_window=an.ps.n_window,
        sample_caps_primary_a=caps, phase_radii_primary_a=phase_radii, provenance=truth['provenance'])


def summary(rows):
    valid = [r for r in rows if r['status'] == 'evaluated']
    within = [r for r in valid if r['assumptions_satisfied']]
    keys = ('evaluated_observations', 'conditional_pass_observations', 'withheld_observations',
            'within_assumption_bound_misses', 'out_of_scope_radius_exceedances', 'conditional_physical_error_above_5pct')
    return dict(planned_records=len(rows), evaluated_records=len(valid), failed_records=len(rows)-len(valid),
        bounded_assumption_records=len(within), assumption_violating_records=len(valid)-len(within),
        within_assumption_observations=sum(r['evaluated_observations'] for r in within),
        **{k: sum(r[k] for r in valid) for k in keys},
        maximum_within_assumption_error_over_radius=max((r['maximum_error_over_radius'] for r in within), default=None),
        maximum_matched_kernel_physical_bias_primary_a=max((r['maximum_matched_kernel_physical_bias_primary_a'] for r in valid), default=None))


def run():
    grid = list(case_grid())
    if not grid:
        raise ValueError('Empty sequence-budget configuration.')
    for config in grid:
        validate(**config)
    rows = []
    for case_id, config in enumerate(grid, 1):
        base = dict(case_id=case_id, **config)
        try:
            with tempfile.TemporaryDirectory(prefix='dr-sequence-budget-') as directory:
                rec, ideal, caps, truth = records(Path(directory), **config)
                row = dict(base, **evaluate(rec, ideal, caps, truth))
            json.dumps(row, allow_nan=False)
        except Exception as error:
            row = dict(base, status='failed', error_type=type(error).__name__, reason=str(error))
        rows.append(row)
    result = summary(rows)
    failed = result['failed_records'] or result['within_assumption_bound_misses'] or not result['within_assumption_observations']
    paths = ['src/dranalyser/dsp/sequence_budget.py', 'tests/test_sequence_budget.py',
        'tests/sequence_budget_records.py', 'scripts/sequence_budget_validation.py',
        'tests/test_sequence_budget_validation.py', 'src/dranalyser/dsp/core.py',
        'src/dranalyser/dsp/pipeline.py', 'src/dranalyser/dsp/detect.py',
        'src/dranalyser/signals.py', 'src/dranalyser/comtrade/parser.py',
        'src/dranalyser/comtrade/timestamps.py', 'docs/superpowers/specs/2026-10-26-sequence-error-budget.md']
    result.update(cases=rows, validation_status='failed' if failed else 'passed_conditional_study',
        authorizes_location=False, production_consumers_changed=False,
        protocol=dict(splits=SPLITS, i2_primary_a=list(I2_VALUES), scenarios=list(SCENARIOS),
            noise_fraction_convention='Hard PEAK sample cap, not Gaussian RMS or a fitted residual bound.',
            seed_policy='split seed+100*I2 index; matched perturbations across amplitudes.',
            absolute_comparison_tolerance_a=ABSOLUTE_TOLERANCE_A, relative_comparison_tolerance=RELATIVE_TOLERANCE),
        limits='Matched DSP-kernel additive perturbations only under supplied caps. Coherent-bias controls '
               'deliberately violate supplied ADC-only caps. No physical-fundamental, clock, field confidence or location authorization.',
        source_sha256_utf8_lf={p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in paths},
        runtime=dict(python=sys.version.split()[0], numpy=np.__version__))
    for key in ('split', 'scenario', 'i2'):
        result['by_'+key] = {str(value): summary([r for r in rows if r[key] == value]) for value in sorted({r[key] for r in rows})}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; choose a new evidence path.')
    result = run()
    content = json.dumps(result, indent=2, allow_nan=False)+'\n'
    try:
        with args.output.open('x', encoding='utf-8', newline='\n') as output:
            output.write(content)
    except FileExistsError:
        parser.error('Output appeared during computation; prior evidence preserved.')
    print(json.dumps({k: result[k] for k in ('planned_records', 'failed_records', 'validation_status') if k in result}))
    return 2 if result['validation_status'] == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
