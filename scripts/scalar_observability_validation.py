"""Frozen scalar necessary-condition study; candidate is never operational authority."""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

from dranalyser.dsp.clock_quality import clock_quality  # noqa: E402
from dranalyser.dsp.pipeline import analyse  # noqa: E402
from dranalyser.faultloc.ensemble import TerminalInput, locate  # noqa: E402
from dranalyser.faultloc.scalar_quality import POLICY, scalar_observability  # noqa: E402
from dranalyser.registry.model import uniform_line  # noqa: E402
from scripts.full_record_quality import truth_errors  # noqa: E402
from tests.scalar_observability_records import FAULTS, SCENARIOS, SECTIONS, SPLITS, records, validate  # noqa: E402


def case_grid():
    return [dict(split=s, profile=p, fault=f, scenario=c) for s, spec in SPLITS.items()
            for p, f, c in itertools.product(spec['profiles'], FAULTS, SCENARIOS)]


def evaluate(pair, truth, *, split):
    line = uniform_line('SYNTHETIC-SCALAR', 'Independent uniform scalar study', 220, 120, SECTIONS[0][1], SECTIONS[0][2])
    analyses = {end: analyse(rec) for end, rec in pair.items()}
    terminals = {end: TerminalInput(an, end) for end, an in analyses.items()}
    loc = locate(line, terminals)
    candidate = scalar_observability(terminals, fault=loc.fault_type)
    baseline = dict(status='located' if loc.ok else 'withheld', method=loc.method, measured_fault=loc.fault_type,
                    reason='; '.join(loc.caveats))
    if loc.ok:
        if not np_isfinite(loc.km_from_S):
            raise ArithmeticError('Located scalar result has nonfinite chainage.')
        baseline.update(reported_km=float(loc.km_from_S), error_km=abs(float(loc.km_from_S)-SPLITS[split]['km']))
    overlay = baseline.copy() if candidate['status'] == 'candidate_pass' else dict(status='withheld', reason=candidate['reason'])
    return dict(status='evaluated', candidate=candidate, baseline=baseline, overlay=overlay,
        truth=truth_errors(pair, truth), clock_alignment_eligible=bool(any(clock_quality(r)['alignment_eligible'] for r in pair.values())),
        acquisition={end: dict(record_hash=r.content_hash, fs=r.fs, timing=r.notes['timestamp_recovery'],
            blocked=r.blocked(), fault=analyses[end].fault_type, saturation=analyses[end].saturation.detected,
            clipping=analyses[end].clipping) for end, r in pair.items()})


def np_isfinite(value):
    import math
    return math.isfinite(value)


def summary(rows):
    valid = [r for r in rows if r['status'] == 'evaluated']
    passes = [r for r in valid if r['candidate']['status'] == 'candidate_pass']
    located = [r for r in valid if r['overlay']['status'] == 'located']
    return dict(planned_incidents=len(rows), evaluated_incidents=len(valid), failed_incidents=len(rows)-len(valid),
        candidate_pass=len(passes), candidate_withheld=len(valid)-len(passes),
        baseline_located=sum(r['baseline']['status'] == 'located' for r in valid), overlay_located=len(located),
        baseline_error_above_1km=sum(r['baseline'].get('error_km', 0) > 1 for r in valid),
        overlay_error_above_1km=sum(r['overlay']['error_km'] > 1 for r in located),
        maximum_overlay_error_km=max((r['overlay']['error_km'] for r in located), default=None),
        harmful_measurement_incidents=sum(r['truth']['harmful_measurement'] is True for r in valid),
        harmful_ct_incidents=sum((r['truth']['maximum_ct_current_error'] or 0) > .05 for r in valid),
        harmful_candidate_pass=sum(r['truth']['harmful_measurement'] is True for r in passes),
        harmful_ct_candidate_pass=sum((r['truth']['maximum_ct_current_error'] or 0) > .05 for r in passes),
        balanced_overlay_located=sum(r['fault'] in ('ABC', 'ABCG') for r in located),
        clean_unbalanced_candidate_pass=sum(r['scenario'] == 'clean' and r['fault'] not in ('ABC', 'ABCG') for r in passes),
        clock_alignment_eligible=sum(r['clock_alignment_eligible'] for r in valid),
        withheld_reasons=dict(Counter(t['reason'] for r in valid for t in r['candidate']['terminals'].values() if t['status'] == 'withheld')))


def run():
    grid = list(case_grid())
    if not grid:
        raise ValueError('Empty scalar-observability grid.')
    for config in grid:
        validate(**config)
    rows = []
    for case_id, config in enumerate(grid, 1):
        base = dict(case_id=case_id, **config)
        try:
            with tempfile.TemporaryDirectory(prefix='dr-scalar-quality-') as directory:
                pair, truth = records(Path(directory), **config)
                row = dict(base, **evaluate(pair, truth, split=config['split']))
            json.dumps(row, allow_nan=False)
        except Exception as error:
            row = dict(base, status='failed', error_type=type(error).__name__, reason=str(error))
        rows.append(row)
    result = summary(rows)
    by_split = {s: summary([r for r in rows if r['split'] == s]) for s in SPLITS}
    complete = len(grid) == 616 and len({tuple(sorted(r.items())) for r in grid}) == 616
    reasons = []
    for bad, reason in [(not complete, 'Incomplete frozen616 grid.'), (result['failed_incidents'], 'Numerical failures.'),
            (any(not r['harmful_ct_incidents'] for r in by_split.values()), 'Missing harmful CT coverage in a split.'),
            (result['harmful_candidate_pass'], 'Harmful measurements pass necessary conditions.'),
            (result['overlay_error_above_1km'], 'Overlay located errors exceed1km.'),
            (result['balanced_overlay_located'], 'Balanced controls acquired overlay locations.'),
            (any(not r['clean_unbalanced_candidate_pass'] for r in by_split.values()), 'No clean unbalanced pass in a split.')]:
        if bad:
            reasons.append(reason)
    paths = [str(p.relative_to(ROOT)).replace('\\', '/') for folder in ('dsp', 'faultloc', 'comtrade', 'registry')
             for p in (ROOT/'src/dranalyser'/folder).glob('*.py')]
    paths += ['src/dranalyser/signals.py', 'scripts/scalar_observability_validation.py',
        'tests/scalar_observability_records.py', 'tests/full_record_acquisition.py',
        'tests/source_fault_oracle.py', 'tests/ct_quality_oracle.py', 'scripts/full_record_quality.py',
        'scripts/acquisition_ct_validation.py', 'tests/test_scalar_quality.py',
        'tests/test_scalar_observability_validation.py', 'docs/superpowers/specs/2026-10-27-scalar-observability.md']
    result.update(cases=rows, by_split=by_split, adoption_gate='failed' if reasons else 'passed_bounded_study',
        adoption_failure_reasons=reasons, authorizes_location=False, production_consumers_changed=False,
        protocol=dict(splits=SPLITS, sections=repr(SECTIONS), scenarios=list(SCENARIOS), faults=list(FAULTS), policy=POLICY,
            comparison='Measured consensus only; baseline legacy scalar output is retained, overlay only suppresses.',
            truth='Independent nodal states, memoryless toy CT, interpolated complete-cycle quadrature; not EMT or field calibration.'),
        source_sha256_utf8_lf={p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in sorted(set(paths))},
        limits='Necessary conditions cannot certify gain/polarity/CT/alias/clock or total error. Candidate and research DSP remain offline.')
    for key in ('scenario', 'fault', 'profile'):
        result['by_'+key] = {v: summary([r for r in rows if r[key] == v]) for v in sorted({r[key] for r in rows})}
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
    print(json.dumps({k: result[k] for k in ('planned_incidents', 'failed_incidents', 'adoption_gate') if k in result}))
    return 2 if result['failed_incidents'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
