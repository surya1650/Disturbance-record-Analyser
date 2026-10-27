"""Frozen conditional E5 error-set experiment; no field calibration or authority."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

from dranalyser.faultloc.error_sets import (  # noqa: E402
    BoundedTerminal, PairedObservation, SeriesSection, e5_error_feasible,
)
from tests.error_set_oracle import case_grid, make_case  # noqa: E402

SOURCES = ['src/dranalyser/faultloc/error_sets.py', 'scripts/e5_error_validation.py',
           'tests/error_set_oracle.py', 'tests/section_network_oracle.py',
           'tests/test_error_sets.py', 'tests/test_e5_error_validation.py',
           'tests/full_record_signals.py', 'docs/superpowers/specs/2026-10-27-e5-error-sets.md']


def evaluate(case):
    observations = []
    for support in case['supports']:
        v, i, vr, ir = support['measured']
        rv, ri, rvr, rir = support['caps']
        observations.append(PairedObservation(BoundedTerminal(v, i, rv, ri, 'synthetic declared total errors'),
                            BoundedTerminal(vr, ir, rvr, rir, 'synthetic declared total errors')))
    result = e5_error_feasible(observations, sections=[SeriesSection(*s) for s in case['sections']],
                               model_provenance='Exact synthetic passive series Z2=Z1 circuit')
    contained = any(lo <= case['m'] <= hi for lo, hi in result['intervals_pu'])
    max_errors = [max(abs(s['measured'][j]-s['truth'][j]) for s in case['supports']) for j in range(4)]
    serialize_complex = lambda v: [float(complex(v).real), float(complex(v).imag)]  # noqa: E731
    return dict(status='evaluated', caps_cover_truth=case['caps_cover_truth'], truth_contained=contained,
                physical_m=case['m'], maximum_actual_errors=max_errors, kcl_residual=case['kcl_residual'],
                supports=[dict(measured=[serialize_complex(v) for v in s['measured']],
                    truth=[serialize_complex(v) for v in s['truth']], caps=s['caps']) for s in case['supports']],
                result=result)


def run(*, grid=None):
    grid = case_grid() if grid is None else grid
    rows = []
    for number, config in enumerate(grid, 1):
        try:
            row = dict(case_id=number, config=config, **evaluate(make_case(config)))
            json.dumps(row, allow_nan=False)
        except Exception as exc:
            row = dict(case_id=number, config=config, status='failed', error_type=type(exc).__name__, reason=str(exc))
        rows.append(row)
    evaluated = [r for r in rows if r['status'] == 'evaluated']
    within = [r for r in evaluated if r['caps_cover_truth']]
    outside = [r for r in evaluated if not r['caps_cover_truth']]
    failures = len(rows)-len(evaluated)
    omissions = sum(not r['truth_contained'] for r in within)
    complete = grid == case_grid() and len(grid) == 556
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', *SOURCES], cwd=ROOT, text=True).strip()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    return dict(planned=len(grid), evaluated=len(evaluated), failed=failures, protocol_complete=complete,
        within_cap_cases=len(within), violated_cap_cases=len(outside), within_cap_truth_omissions=omissions,
        violated_cap_truth_exclusions=sum(not r['truth_contained'] for r in outside),
        status_counts=dict(Counter(r['result']['status'] for r in evaluated)),
        total_boxes_evaluated=sum(r['result']['boxes_evaluated'] for r in evaluated),
        maximum_width_pu=max((r['result']['total_width_pu'] for r in within), default=None),
        study_gate='passed_conditional_numerical' if complete and not failures and not omissions and not dirty else 'failed',
        authorizes_location=False, cases=rows, source_git_revision=revision, sources_clean=not bool(dirty),
        source_sha256_utf8_lf={p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in SOURCES},
        runtime=dict(python=platform.python_version(), numpy=np.__version__),
        limitations='Necessary numerical outer sets, not formal floating intervals/calibrated confidence. Caller caps/model not authenticated; no shared-phase test or production authorization.')


def publish(result, path):
    content = json.dumps(result, indent=2, allow_nan=False)+'\n'
    with path.open('x', encoding='utf-8', newline='\n') as output:
        output.write(content)
    return 0 if not result['failed'] and result.get('study_gate') == 'passed_conditional_numerical' else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; preserve earlier evidence.')
    result = run()
    try:
        status = publish(result, args.output)
    except FileExistsError:
        parser.error('Output appeared during computation; prior evidence preserved.')
    print(json.dumps({k: result[k] for k in ('planned', 'failed', 'within_cap_truth_omissions', 'study_gate')}))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
