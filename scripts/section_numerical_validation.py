"""Offline phase-nodal section experiment; requires the source checkout's tests.

No production synthetic generator or locator equation constructs fault truth.
This is phasor-level numerical evidence, not EMT/acquisition or field validation.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

import numpy as np  # noqa: E402

from dranalyser.faultloc.sections import section_window  # noqa: E402
from dranalyser.registry.model import Line, LineSection  # noqa: E402
from tests.section_network_oracle import negative, solve  # noqa: E402


GEOMETRIES = [
    [(40, .03+.25j, .4+1.4j), (60, .3+.7j, .1+1j)],
    [(40, .03+.25j, .1+.75j), (60, .06+.5j, .2+1.5j)],
    [(25, .1+.6j, .4+1.1j), (35, .25+.4j, .7+1.5j), (40, .04+.2j, .2+.9j)],
]
SCENARIOS = ('ideal', 'noise_0.1pct', 'noise_1pct', 'noise_5pct',
             'remote_current_plus10pct', 'first_section_z_plus20pct', 'remote_polarity_reversed')


def model(sections):
    line = Line('SYNTHETIC-SECTIONS', 'Independent phase nodal study', 220, [], {})
    start = 0
    for i, (length, z1, z0) in enumerate(sections):
        line.sections.append(LineSection(i+1, start, start+length, z1.real, z1.imag, z0.real, z0.imag))
        start += length
    return line


def summarize(rows):
    good = [r for r in rows if r['status'] == 'located']
    errors = [r['error_km'] for r in good]
    return dict(planned=len(rows), located=len(good), refused=len(rows)-len(good),
        p95_error_km=float(np.percentile(errors, 95)) if errors else None,
        max_error_km=float(max(errors)) if errors else None,
        worst_located_case=max(good, key=lambda r: r['error_km']) if good else None,
        descriptive_spread_contains_truth=sum(int(r['contains_truth']) for r in good),
        refusal_reasons=dict(sorted(Counter(r['reason'] for r in rows if r['status'] != 'located').items())))


def run(seed=854):
    rng = np.random.default_rng(seed)
    rows = {name: [] for name in SCENARIOS}
    max_kcl = 0.0
    for geometry, original in enumerate(GEOMETRIES):
        for km in (1, 25, 40, 50, 60, 75, 99):
            for phase in range(3):
                for resistance in (1, 50):
                    for reverse in (False, True):
                        sections = original[::-1] if reverse else original
                        position = 100-km if reverse else km
                        state = solve(sections, position, phase, resistance, reverse_sources=reverse)
                        max_kcl = max(max_kcl, state['residual'])
                        truth = np.array([negative(state[k]) for k in ('VS', 'IS', 'VR', 'IR')])
                        for aligned, rotation in ((True, 0), (False, 0), (False, -2.4), (False, 1.1)):
                            base = np.repeat(truth[:, None], 8, axis=1)
                            base[2:] *= np.exp(1j*rotation)
                            for scenario in SCENARIOS:
                                line, values = model(sections), base.copy()
                                if scenario.startswith('noise_'):
                                    fraction = float(scenario.split('_')[1].removesuffix('pct'))/100
                                    scales = np.array([max(abs(truth[0]), abs(truth[2])),
                                                       max(abs(truth[1]), abs(truth[3]))]*2)
                                    values += fraction*scales[:, None]*(rng.normal(size=values.shape)+
                                                                       1j*rng.normal(size=values.shape))/np.sqrt(2)
                                elif scenario == 'remote_current_plus10pct':
                                    values[3] *= 1.1
                                elif scenario == 'first_section_z_plus20pct':
                                    line = copy.deepcopy(line)
                                    line.sections[0].r1 *= 1.2
                                    line.sections[0].x1 *= 1.2
                                elif scenario == 'remote_polarity_reversed':
                                    values[3] *= -1
                                result = section_window(line, *values, aligned=aligned)
                                row = dict(status=result['status'], reason=result['reason'],
                                           mode='aligned' if aligned else 'unsynchronised',
                                           geometry=geometry, true_km=position, phase=phase,
                                           resistance_ohm=resistance, reversed=reverse, remote_rotation_rad=rotation)
                                if result['status'] == 'located':
                                    lo, hi = (line.m_to_km(m) for m in result['interval_pu'])
                                    rounding = 32*np.finfo(float).eps*100
                                    row.update(error_km=float(abs(result['km_from_S']-position)),
                                               reported_km=result['km_from_S'],
                                               contains_truth=bool(lo-rounding <= position <= hi+rounding))
                                rows[scenario].append(row)
    results = {}
    for name, cases in rows.items():
        results[name] = summarize(cases)
        results[name]['by_mode'] = {mode: summarize([r for r in cases if r['mode'] == mode])
                                    for mode in ('aligned', 'unsynchronised')}
    paths = ['src/dranalyser/faultloc/sections.py', 'src/dranalyser/faultloc/section_location.py',
             'src/dranalyser/faultloc/stage_location.py', 'tests/section_network_oracle.py',
             'scripts/section_numerical_validation.py']
    return dict(seed=seed, planned=sum(r['planned'] for r in results.values()),
        located=sum(r['located'] for r in results.values()), refused=sum(r['refused'] for r in results.values()),
        scenarios=results, max_oracle_kcl_residual_a=max_kcl,
        source_sha256_utf8_lf={p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
                              for p in paths},
        protocol=dict(geometry_count=3, chainages_km=[1, 25, 40, 50, 60, 75, 99], phases=['AG', 'BG', 'CG'],
                      fault_resistance_ohm=[1, 50], reversal=True, samples_per_window=8,
                      modes=['aligned@0', 'unsynchronised@0', 'unsynchronised@-2.4rad', 'unsynchronised@1.1rad'],
                      noise='Complex Gaussian RMS relative to stronger V2/I2 terminal, independent at each sample.',
                      spread_roundoff_km=32*np.finfo(float).eps*100),
        limits='Synthetic phase-nodal phasors, Z2=Z1; fixed source impedances, no charging/coupling/EMT, '
               'no field accuracy, calibrated confidence or safety guarantee for undeclared parameter/polarity bias.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=854)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        with args.output.open('x', encoding='utf-8') as handle:
            result = run(args.seed)
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write('\n')
    except FileExistsError:
        parser.error('Output already exists; choose a new evidence path.')
    print(json.dumps({k: result[k] for k in ('planned', 'located', 'refused')}))


if __name__ == '__main__':
    main()
