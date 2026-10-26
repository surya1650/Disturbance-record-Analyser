"""Frozen three-phase/full-record CT and acquisition experiment; source checkout."""
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

from dranalyser.dsp.clock_quality import clock_quality  # noqa: E402
from scripts.acquisition_quality_candidate import POLICY  # noqa: E402
from scripts.full_record_quality import record_quality, truth_errors  # noqa: E402
from scripts.noisy_dsp_validation import evaluate  # noqa: E402
from tests.full_record_acquisition import records  # noqa: E402
from tests.full_record_signals import FAULTS, SCENARIOS, SPLITS, validate  # noqa: E402


def case_grid():
    return [dict(split=split, profile=profile, fault=fault, scenario=scenario)
            for split, spec in SPLITS.items()
            for profile, fault, scenario in itertools.product(spec['profiles'], FAULTS, SCENARIOS)]


def summary(rows):
    workflows = [dict(case_id=row['case_id'], fault=row['fault'], scenario=row['scenario'], workflow=name, **value)
                 for row in rows for name, value in row['workflows'].items()]
    located = [r for r in workflows if r['status'] == 'located']
    evaluated = [r for r in rows if r['status'] == 'evaluated']
    quality_pass = [r for r in evaluated if all(v['status'] == 'candidate_pass' for v in r['quality'].values())]
    errors = [r['error_km'] for r in located]
    return dict(incidents=len(rows), evaluated_incidents=len(evaluated), planned=len(workflows),
        located=len(located), refused=sum(r['status'] == 'withheld' for r in workflows),
        failed=sum(r['status'] == 'failed' for r in workflows), quality_pass_incidents=len(quality_pass),
        harmful_measurement_incidents=sum(r['truth']['harmful_measurement'] is True for r in evaluated),
        harmful_quality_pass=sum(r['truth']['harmful_measurement'] is True for r in quality_pass),
        harmful_ct_incidents=sum((r['truth']['maximum_ct_current_error'] or 0) > .05 for r in evaluated),
        harmful_ct_quality_pass=sum((r['truth']['maximum_ct_current_error'] or 0) > .05 for r in quality_pass),
        balanced_located=sum(r['fault'] == 'ABC' for r in located),
        located_error_above_1km=sum(e > 1 for e in errors),
        p95_error_km=float(np.percentile(errors, 95)) if errors else None,
        maximum_error_km=max(errors) if errors else None,
        worst_located=max(located, key=lambda r: r['error_km']) if located else None,
        e4_outcomes=sum(r.get('method', '').startswith('E4') for r in workflows))


def run():
    grid = list(case_grid())
    if not grid:
        raise ValueError('Empty full-record experiment configuration.')
    for config in grid:
        validate(**config)
    rows = []
    for case_id, config in enumerate(grid, 1):
        base = dict(case_id=case_id, **config)
        try:
            with tempfile.TemporaryDirectory(prefix='dr-full-record-') as directory:
                pair, truth = records(Path(directory), **config)
                actual = evaluate(pair)
                row = dict(base, status='evaluated', truth=truth_errors(pair, truth),
                    quality={end: record_quality(rec, actual['frequency_hz'][end], truth[end]['window_indices'])
                             for end, rec in pair.items()},
                    acquisition={end: dict(record_hash=rec.content_hash, fs=rec.fs,
                        frequency_hz=actual['frequency_hz'][end], clock_quality=clock_quality(rec),
                        block_codes=[f.code for f in rec.flags if f.severity == 'block'],
                        timestamp_recovery=rec.notes.get('timestamp_recovery'), dsp=actual['quality'][end])
                        for end, rec in pair.items()},
                    workflows={name: actual[name] for name in ('main', 'stage')})
            for value in row['workflows'].values():
                if value['status'] not in ('located', 'withheld'):
                    raise ValueError('Invalid actual workflow status.')
                if value['status'] == 'located' and not np.all(np.isfinite([value['reported_km'], value['error_km']])):
                    raise ArithmeticError('Nonfinite located chainage.')
            json.dumps(row, allow_nan=False)  # Both workflows commit together, including every diagnostic.
        except Exception as error:
            failure = dict(status='failed', error_type=type(error).__name__, reason=str(error))
            row = dict(base, **failure, workflows={name: dict(failure) for name in ('main', 'stage')})
        rows.append(row)
    result = summary(rows)
    groups = {field: {str(value): summary([r for r in rows if r[field] == value])
                     for value in sorted({r[field] for r in rows})}
              for field in ('split', 'profile', 'fault', 'scenario')}
    validation = groups['split'].get('validation', summary([]))
    reasons = []
    for condition, reason in [(result['failed'], 'Numerical failures.'),
            (not validation['harmful_ct_incidents'], 'No harmful validation CT coverage.'),
            (result['harmful_quality_pass'], 'Harmful measurements passed joint shape/acquisition screens.'),
            (result['located_error_above_1km'], 'Actual located error above 1 km.'),
            (result['balanced_located'], 'Balanced controls located.')]:
        if condition:
            reasons.append(reason)
    paths = ['scripts/full_record_validation.py', 'scripts/full_record_quality.py',
        'tests/full_record_acquisition.py', 'tests/full_record_signals.py',
        'tests/test_full_record_acquisition.py', 'tests/test_full_record_validation.py',
        'scripts/acquisition_quality_candidate.py', 'scripts/acquisition_ct_validation.py',
        'tests/ct_quality_oracle.py', 'tests/source_fault_oracle.py', 'scripts/noisy_dsp_validation.py',
        'scripts/source_fault_validation.py', 'src/dranalyser/signals.py',
        'src/dranalyser/comtrade/parser.py', 'src/dranalyser/comtrade/timestamps.py',
        'src/dranalyser/dsp/core.py', 'src/dranalyser/dsp/detect.py', 'src/dranalyser/dsp/pipeline.py',
        'src/dranalyser/dsp/stage_windows.py', 'src/dranalyser/dsp/stages.py',
        'src/dranalyser/workbench/stage_review.py', 'src/dranalyser/workbench/stage_location.py',
        'src/dranalyser/faultloc/section_location.py', 'src/dranalyser/faultloc/sections.py',
        'src/dranalyser/faultloc/stage_location.py', 'src/dranalyser/faultloc/ensemble.py',
        'src/dranalyser/rules/evidence.py', 'src/dranalyser/rules/stages.py',
        'docs/superpowers/specs/2026-10-26-three-phase-acquisition.md']
    return dict(result, **{'by_'+k: v for k, v in groups.items()}, cases=rows,
        adoption_gate='failed' if reasons else 'passed_bounded_study', adoption_failure_reasons=reasons,
        production_gates_changed=False, scalar_current_policy=POLICY,
        voltage_shape_policy=dict(relative_budgets='same frozen scalar math', minimum_fundamental_rms_secondary_v=1e-9),
        protocol=dict(splits=SPLITS, scenarios=list(SCENARIOS), faults=list(FAULTS), true_km=75,
            adc_bits=20, current_ratio=1000, voltage_ratio=2000, full_scale_secondary=dict(I=64, V=150),
            noise='Family RMS reference over ideal capture; seed=split seed+100*profile index+10*fault index.',
            truth_window='Known synthetic inception+1.5 cycles to clearing-.5 cycle, sample indices; no field identity inference.'),
        limits='Offline synthetic state splices and toy CT/ideal VT; no EMT, anti-alias-filter, '
               'hysteresis/remanence, manufacturer model, calibrated confidence, field acceptance or clock promotion.',
        source_sha256_utf8_lf={p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in paths},
        runtime=dict(python=sys.version.split()[0], numpy=np.__version__))


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
    print(json.dumps({k: result[k] for k in ('incidents', 'planned', 'failed', 'adoption_gate') if k in result}))
    return 2 if result['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
