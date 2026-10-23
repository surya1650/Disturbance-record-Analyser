"""Independent source/fault phasor envelope and actual-DSP guarded controls.

Requires the source checkout's test oracles. All results are synthetic; raw
solver output, measured sequence screening and operational scope are distinct.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

import numpy as np  # noqa: E402

from dranalyser.faultloc.sections import section_window  # noqa: E402
from dranalyser.registry.model import Line, LineSection, Terminal  # noqa: E402
from tests.source_fault_oracle import FAULTS, PROFILES, sequence, solve, source_pair  # noqa: E402

GEOMETRIES = [
    [(40, .03+.25j, .4+1.4j), (60, .3+.7j, .1+1j)],
    [(25, .1+.6j, .4+1.1j), (35, .25+.4j, .7+1.5j), (40, .04+.2j, .2+.9j)],
]
REFERENCES = ((True, 0), (False, 0), (False, 1.1))
NOISE = {'ideal': 0, 'noise_0.1pct': .001, 'noise_1pct': .01}
BALANCED = ('ABC', 'ABCG')


def model(sections):
    line = Line('SYNTHETIC-SOURCE-FAULT', 'Independent source/fault validation', 220, [],
                {end: Terminal(end, end) for end in ('S', 'R')})
    start = 0
    for i, (length, z1, z0) in enumerate(sections):
        line.sections.append(LineSection(i+1, start, start+length, z1.real, z1.imag, z0.real, z0.imag))
        start += length
    line.section_solver_enabled = True
    return line


def summarize(rows, *, witness=True):
    located = [r for r in rows if r['status'] == 'located']
    errors = [r['error_km'] for r in located]
    coverage = [r['contains_truth'] for r in located if r.get('contains_truth') is not None]
    out = dict(planned=len(rows), located=len(located), refused=len(rows)-len(located),
               p95_error_km=float(np.percentile(errors, 95)) if errors else None,
               max_error_km=float(max(errors)) if errors else None,
               located_error_above_1km=sum(e > 1 for e in errors),
               descriptive_spread_evaluated=len(coverage),
               descriptive_spread_contains_truth=sum(int(c) for c in coverage),
               refusal_reasons=dict(sorted(Counter(r['reason'] for r in rows if r['status'] != 'located').items())))
    if witness:
        out['worst_located_case'] = max(located, key=lambda r: r['error_km']) if located else None
    return out


def cohorts(rows):
    unbalanced = [r for r in rows if r['fault'] not in BALANCED]
    screened = [dict(r, status='withheld', reason='Measured negative-sequence strength screen failed.')
                if not r['strength_eligible'] else r for r in unbalanced]
    return dict(unbalanced=summarize(unbalanced), screened_unbalanced=summarize(screened),
                balanced_controls=summarize([r for r in rows if r['fault'] in BALANCED]))


def infeed_bin(ratio, signal_present):
    if not signal_present:
        return 'absent_negative_sequence'
    for upper, label in [(1e-4, '<=1e-4'), (.01, '1e-4..1e-2'), (.1, '1e-2..1e-1')]:
        if ratio <= upper:
            return label
    return '>1e-1'


def measurement_scales(negative, positive_voltage, positive_currents):
    """Nonzero sensor-noise floor even when the negative sequence is absent."""
    return np.array([max(abs(negative[0]), abs(negative[2]), .01*positive_voltage),
                     max(abs(negative[1]), abs(negative[3]), .01*max(positive_currents))]*2)


def run(seed=854):
    rng = np.random.default_rng(seed)
    all_rows = {name: [] for name in NOISE}
    max_residual, case_id = 0.0, 0
    for geometry, original in enumerate(GEOMETRIES):
        for km in (10, 40, 75):
            for profile in PROFILES:
                sources = source_pair(profile)
                for fault in FAULTS:
                    for resistance in (1, 50):
                        for reverse in (False, True):
                            sections = original[::-1] if reverse else original
                            position = 100-km if reverse else km
                            state = solve(sections, position, fault, resistance, sources=sources, reverse_sources=reverse)
                            max_residual = max(max_residual, state['residual'])
                            q = np.array([sequence(state[k], 2) for k in ('VS', 'IS', 'VR', 'IR')])
                            v1 = max(abs(sequence(state[k], 1)) for k in ('VS', 'VR'))
                            i1 = np.array([abs(sequence(state[k], 1)) for k in ('IS', 'IR')])
                            scales = measurement_scales(q, v1, i1)
                            for aligned, rotation in REFERENCES:
                                reference = 'aligned' if aligned else f'unsynchronised@{rotation}'
                                base = np.repeat(q[:, None], 8, axis=1)
                                base[2:] *= np.exp(1j*rotation)
                                for scenario, noise in NOISE.items():
                                    case_id += 1
                                    values = base.copy()
                                    if noise:
                                        values += noise*scales[:, None]*(rng.normal(size=values.shape)+
                                                                        1j*rng.normal(size=values.shape))/np.sqrt(2)
                                    currents = np.median(abs(values[[1, 3]]), axis=1)
                                    ratio = float(min(currents)/max(max(currents), 1e-300))
                                    signal_present = bool(max(currents) >= max(1e-6, .01*max(i1)))
                                    eligible = bool(np.all(np.min(abs(values[[1, 3]]), axis=1) >= np.maximum(.01*i1, 1e-6)))
                                    line = model(sections)
                                    result = section_window(line, *values, aligned=aligned)
                                    row = dict(case_id=case_id, scenario=scenario, geometry=geometry, profile=profile,
                                               fault=fault, resistance_ohm=resistance, reversed=reverse,
                                               true_km=position, reference=reference, remote_rotation_rad=rotation,
                                               measured_infeed_ratio=ratio, infeed_bin=infeed_bin(ratio, signal_present),
                                               strength_eligible=eligible, source_fault=profile+'/'+fault,
                                               status=result['status'], reason=result['reason'])
                                    if result['status'] == 'located':
                                        lo, hi = (line.m_to_km(m) for m in result['interval_pu'])
                                        rounding = 32*np.finfo(float).eps*line.length_km
                                        row.update(reported_km=result['km_from_S'], error_km=abs(result['km_from_S']-position),
                                                   contains_truth=bool(lo-rounding <= position <= hi+rounding))
                                    all_rows[scenario].append(row)
    result = summarize([r for rows in all_rows.values() for r in rows])
    scenarios = {}
    for name, rows in all_rows.items():
        summary = summarize(rows)
        summary.update(cohorts(rows))
        for key, field in [('by_profile', 'profile'), ('by_fault', 'fault'), ('by_reference', 'reference'),
                           ('by_infeed_ratio', 'infeed_bin'), ('by_source_fault', 'source_fault')]:
            summary[key] = {}
            for value in sorted({r[field] for r in rows}):
                subset = [r for r in rows if r[field] == value]
                group = summarize(subset, witness=key != 'by_source_fault')
                if key in ('by_profile', 'by_reference', 'by_infeed_ratio'):
                    group.update(cohorts(subset))
                summary[key][value] = group
        scenarios[name] = summary
    paths = ['scripts/source_fault_validation.py', 'tests/source_fault_oracle.py', 'tests/source_fault_records.py',
             'tests/test_source_fault_oracle.py', 'tests/test_source_fault_validation.py', 'tests/test_source_fault_integration.py',
             'src/dranalyser/faultloc/sections.py', 'src/dranalyser/faultloc/section_location.py',
             'src/dranalyser/faultloc/stage_location.py', 'src/dranalyser/faultloc/ensemble.py']
    result.update(seed=seed, scenarios=scenarios, max_oracle_kcl_residual_a=max_residual,
        runtime=dict(python=sys.version.split()[0], numpy=np.__version__),
        source_sha256_utf8_lf={p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
                              for p in paths},
        protocol=dict(source_profiles=list(PROFILES), fault_connections=list(FAULTS), geometry_count=2,
                      chainages_km=[10, 40, 75], resistance_ohm=[1, 50], physical_reversal=True,
                      references=[[a, r] for a, r in REFERENCES], samples_per_window=8,
                      noise_positive_sequence_floor_fraction=.01,
                      noise='Independent complex Gaussian V2/I2; stronger negative terminal or 1% of stronger V1/I1.',
                      strength_screen='Every I2 observation >=max(.01*ideal terminal |I1|,1e-6 A); positive references held ideal.',
                      balanced_controls='Raw diagnostics only; never operational balanced-fault acceptance.',
                      interval_roundoff_km=32*np.finfo(float).eps*100),
        limits='Raw phasor windows, not guarded records. Balanced controls and measured-strength screening are separate; '
               'no EMT, line coupling/charging, CT-zone terminal faults, calibrated confidence or field accuracy.')
    return result


def guarded_cases():
    """88 one-step synthetic incidents per workflow, no phasor replacement."""
    from dranalyser.dsp.pipeline import analyse
    from dranalyser.faultloc.ensemble import TerminalInput, locate
    from dranalyser.rules.evidence import relay_evidence
    from dranalyser.workbench.stage_location import stage_locations
    from dranalyser.workbench.stage_review import apply_stage_review
    from tests.source_fault_records import records

    rows = {'main': [], 'stage': []}
    for profile in PROFILES:
        for fault in FAULTS:
            line = model(GEOMETRIES[0])
            analyses = {end: analyse(rec) for end, rec in records(GEOMETRIES[0], 75, fault, profile=profile).items()}
            main = locate(line, {end: TerminalInput(an, end) for end, an in analyses.items()})
            evidence = []
            for end, an in analyses.items():
                row = relay_evidence(an, end+'.cfg', end, protection_system='Main-1')
                apply_stage_review(row, line_id=line.id, incident_id='synthetic-source-fault')
                active = [s for s in row['stages']['intervals'] if s['stable'] and s['phase_pattern']]
                groups = {max(active, key=lambda s: s['end_s']-s['start_s'])['id']: 'known-synthetic-fault'} if active else {}
                review = dict(inventory_hash=row['stages']['inventory_hash'], reviewer='Synthetic network validation',
                              reason='Known one-step physical source/fault schedule; synthetic only', groups=groups,
                              same_incident=True, same_circuit=True, stage_identity=True, location_requested=True)
                apply_stage_review(row, review, line.id, 'synthetic-source-fault')
                evidence.append(row)
            stages = stage_locations(line, analyses, evidence, {'S': 'S.cfg', 'R': 'R.cfg'})
            stage = stages[0] if stages else dict(status='withheld', reason='No matched eligible reviewed stage.')
            for workflow, located, km, reason in [
                    ('main', main.ok, main.km_from_S, '; '.join(main.caveats)),
                    ('stage', stage['status'] == 'located', stage.get('km_from_S'), stage['reason'])]:
                out = dict(profile=profile, fault=fault, status='located' if located else 'withheld', reason=reason)
                if located:
                    out.update(reported_km=km, error_km=abs(km-75))
                rows[workflow].append(out)
    return {name: dict(summarize(cases),
                       unbalanced=summarize([r for r in cases if r['fault'] not in BALANCED]),
                       balanced_controls=summarize([r for r in cases if r['fault'] in BALANCED]), cases=cases)
            for name, cases in rows.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=854)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        with args.output.open('x', encoding='utf-8') as handle:
            result = run(args.seed)
            result['guarded_actual_dsp'] = guarded_cases()
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write('\n')
    except FileExistsError:
        parser.error('Output already exists; choose a new evidence path.')
    print(json.dumps({k: result[k] for k in ('planned', 'located', 'refused')}))


if __name__ == '__main__':
    main()
