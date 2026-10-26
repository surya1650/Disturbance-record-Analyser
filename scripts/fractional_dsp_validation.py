"""Frozen disjoint physical-fundamental validation; no field/location authority."""
import argparse
from functools import partial
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'src'))

from scripts.sequence_budget_validation import evaluate as metrology_evaluate, summary  # noqa: E402
from tests.sequence_budget_records import I2_VALUES, SCENARIOS, SPLITS  # noqa: E402

NEW_SPLITS = {'development': dict(freq=47, fs=3200, pre=.16, angle=.53, seed=4754),
              'validation': dict(freq=53, fs=4100, pre=.19, angle=1.17, seed=5954)}
PHYSICAL_BIAS_LIMIT_A = .01
evaluate = partial(metrology_evaluate, method='basis')


def case_grid():
    return [dict(split=s, i2=i, scenario=c) for s, i, c in itertools.product(NEW_SPLITS, I2_VALUES, SCENARIOS)]


def _source(splits):
    # Independent function globals avoid mutating the historical generator.
    spec = importlib.util.spec_from_file_location('fractional_metrology_source', ROOT/'tests/sequence_budget_records.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SPLITS = {name: values.copy() for name, values in splits.items()}
    return module


def run(*, historical=False):
    splits = SPLITS if historical else NEW_SPLITS
    source = _source(splits)
    grid = list(case_grid())
    if not grid:
        raise ValueError('Empty fractional-DSP configuration.')
    for config in grid:
        source.validate(**config)
    rows = []
    for case_id, config in enumerate(grid, 1):
        base = dict(case_id=case_id, **config)
        try:
            with tempfile.TemporaryDirectory(prefix='dr-fractional-dsp-') as directory:
                row = dict(base, **evaluate(*source.records(Path(directory), **config)))
            json.dumps(row, allow_nan=False)
        except Exception as error:
            row = dict(base, status='failed', error_type=type(error).__name__, reason=str(error))
        rows.append(row)
    result = summary(rows)
    complete = len(grid) == 80 and len({(r['split'], r['i2'], r['scenario']) for r in grid}) == 80
    bias = result['maximum_matched_kernel_physical_bias_primary_a']
    physical_ok = bias is not None and bias < PHYSICAL_BIAS_LIMIT_A
    failed = (result['failed_records'] or result['within_assumption_bound_misses'] or
              not result['within_assumption_observations'] or not physical_ok)
    paths = sorted({
        'src/dranalyser/dsp/core.py', 'src/dranalyser/dsp/fundamental.py',
        'src/dranalyser/dsp/sequence_budget.py', 'src/dranalyser/dsp/pipeline.py',
        'src/dranalyser/dsp/detect.py', 'src/dranalyser/signals.py',
        'src/dranalyser/comtrade/parser.py', 'src/dranalyser/comtrade/timestamps.py',
        'tests/sequence_budget_records.py', 'tests/test_sequence_budget.py',
        'tests/test_sequence_budget_validation.py', 'tests/test_fractional_dsp.py',
        'scripts/sequence_budget_validation.py', 'scripts/fractional_dsp_validation.py',
        'tests/test_fractional_dsp_validation.py', 'docs/superpowers/specs/2026-10-27-fractional-dsp.md'})
    result.update(cases=rows, authorizes_location=False, production_consumers_changed=False,
        complete_grid_gate=bool(complete and not failed), physical_bias_gate=physical_ok,
        validation_status='failed' if failed else 'passed_physical_study' if complete else 'passed_subset_study',
        protocol=dict(grid='historical_replay' if historical else 'new_disjoint_grid', splits=splits,
            i2_primary_a=list(I2_VALUES), scenarios=list(SCENARIOS), physical_bias_limit_a=PHYSICAL_BIAS_LIMIT_A,
            noise_fraction_convention='Hard PEAK caps + ADC half step; coherent controls violate ADC-only caps.',
            absolute_bound_tolerance_a=1e-8, relative_bound_tolerance=1e-8),
        limits='Uniform synthetic supports and correct-frequency sinusoidal model only; no field, frequency-'
            'uncertainty, gain/polarity, CT, anti-alias, clock or location certification. Physical bias is '
            'measured on ideal signals; additive coverage excludes cap-violating controls.',
        source_sha256_utf8_lf={p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in paths})
    for key in ('split', 'scenario', 'i2'):
        result['by_'+key] = {str(v): summary([r for r in rows if r[key] == v]) for v in sorted({r[key] for r in rows})}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--historical', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; choose a new evidence path.')
    result = run(historical=args.historical)
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
