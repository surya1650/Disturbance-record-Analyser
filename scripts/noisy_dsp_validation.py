"""Seeded noisy waveform and local DAT recovery experiment; source checkout required."""
import argparse
from collections import Counter
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

from tests.noisy_dsp_records import records  # noqa: E402
from scripts.source_fault_validation import model  # noqa: E402
from tests.test_source_fault_oracle import SECTIONS  # noqa: E402

PROFILES = ('baseline', 'weak_R_100', 'voltage_unbalance')
FAULTS = ('AG', 'BC', 'ABG', 'ABC')
NOISE = (0, .001, .01)
TIMING = ('declared', 'rounded', 'bounded_jitter', 'clock_skew', 'gap')


def evaluate(pair):
    """Actual DSP and current main/source-bound reviewed-stage dispatch."""
    from dranalyser.dsp.pipeline import analyse
    from dranalyser.faultloc.ensemble import TerminalInput, locate
    from dranalyser.rules.evidence import relay_evidence
    from dranalyser.workbench.stage_location import stage_locations
    from dranalyser.workbench.stage_review import apply_stage_review
    line = model(SECTIONS)
    analyses = {end: analyse(rec) for end, rec in pair.items()}
    main = locate(line, {end: TerminalInput(an, end) for end, an in analyses.items()})
    evidence = []
    for end, an in analyses.items():
        row = relay_evidence(an, end+'.cfg', end, protection_system='Main-1')
        apply_stage_review(row, line_id=line.id, incident_id='synthetic-noisy')
        active = [s for s in row['stages']['intervals'] if s['stable'] and s['phase_pattern']]
        groups = {max(active, key=lambda s: s['end_s']-s['start_s'])['id']: 'known-synthetic-fault'} if active else {}
        review = dict(inventory_hash=row['stages']['inventory_hash'], reviewer='Synthetic noisy validation',
                      reason='Known one-step physical schedule, not field identity', groups=groups,
                      same_incident=True, same_circuit=True, stage_identity=True, location_requested=True)
        if groups:
            apply_stage_review(row, review, line.id, 'synthetic-noisy')
        evidence.append(row)
    stages = stage_locations(line, analyses, evidence, {'S': 'S.cfg', 'R': 'R.cfg'})
    stage = stages[0] if stages else dict(status='withheld', reason='No matched eligible reviewed stage.', method='E5')
    out = {}
    for workflow, located, km, method, reason in [
            ('main', main.ok, main.km_from_S, main.method, '; '.join(main.caveats)),
            ('stage', stage['status'] == 'located', stage.get('km_from_S'), stage['method'], stage['reason'])]:
        result = dict(status='located' if located else 'withheld', method=method, reason=reason,
                      clock_shift_applied=False)
        if located:
            if not np.isfinite(km):
                raise ArithmeticError('Located outcome has nonfinite chainage.')
            result.update(reported_km=float(km), error_km=abs(float(km)-75))
        out[workflow] = result
    out['frequency_hz'] = {end: an.freq for end, an in analyses.items()}
    out['quality'] = {end: dict(saturation_detected=an.saturation.detected,
        saturation_channels=an.saturation.channels, saturation_severity=an.saturation.severity,
        clipping=an.clipping, fault_type=an.fault_type,
        stage_quality_reasons=row['stages']['quality_reasons'],
        stage_window_reasons=[s.get('estimation_window', {}).get('reason') for s in row['stages']['intervals']])
        for (end, an), row in zip(analyses.items(), evidence, strict=True)}
    return out


def summary(rows):
    located = [r for r in rows if r['status'] == 'located']
    errors = [r['error_km'] for r in located]
    return dict(planned=len(rows), located=len(located), refused=sum(r['status'] == 'withheld' for r in rows),
                failed=sum(r['status'] == 'failed' for r in rows),
                p95_error_km=float(np.percentile(errors, 95)) if errors else None,
                max_error_km=max(errors) if errors else None,
                located_error_above_1km=sum(e > 1 for e in errors),
                refusal_reasons=dict(Counter(r['reason'] for r in rows if r['status'] == 'withheld')),
                worst_located_case=max(located, key=lambda r: r['error_km']) if located else None)


def validate_configuration(seed):
    """Reject genuine grid/configuration defects before planned case execution."""
    from tests.source_fault_oracle import PROFILES as known_profiles, FAULTS as known_faults
    from tests.noisy_dsp_records import TIMING as known_timing
    if (not PROFILES or not FAULTS or not NOISE or not TIMING or
            any(p not in known_profiles for p in PROFILES) or any(f not in known_faults for f in FAULTS) or
            any(t not in known_timing for t in TIMING) or any(not np.isfinite(n) or n < 0 for n in NOISE)):
        raise ValueError('Invalid experiment configuration: source/fault/noise/timing grid.')
    np.random.default_rng(seed)  # Validate seed before any source computation or output.
    model(SECTIONS)


def run(seed=854):
    validate_configuration(seed)
    rows = []
    from dranalyser.dsp.clock_quality import clock_quality
    grid = list(itertools.product(PROFILES, FAULTS, NOISE, TIMING))
    for incident, (profile, fault, noise, timing) in enumerate(grid, 1):
        base = dict(incident=incident, profile=profile, fault=fault, noise=noise, timing=timing)
        # Match perturbations across timing modes and noise amplitudes.
        case_seed = seed+100*PROFILES.index(profile)+10*FAULTS.index(fault)
        try:
            with tempfile.TemporaryDirectory(prefix='dr-noisy-') as directory:
                pair = records(Path(directory), fault=fault, profile=profile, noise=noise, timing=timing, seed=case_seed)
                result = evaluate(pair)
                base['acquisition'] = {end: dict(record_hash=r.content_hash,
                    recovery=r.notes['timestamp_recovery'], block_codes=[f.code for f in r.flags if f.severity == 'block'],
                    start_time=r.start_time.isoformat(), trigger_time=r.trigger_time.isoformat(),
                    clock_quality=clock_quality(r), recovered_fs=r.fs, frequency_hz=result['frequency_hz'][end],
                    dsp_quality=result['quality'][end])
                    for end, r in pair.items()}
            candidates = [dict(base, workflow=workflow, **result[workflow]) for workflow in ('main', 'stage')]
            for row in candidates:
                if row['status'] not in ('located', 'withheld'):
                    raise ValueError('Invalid workflow status in numerical case output.')
                if row['status'] == 'located' and not np.all(np.isfinite([row['reported_km'], row['error_km']])):
                    raise ValueError('Nonfinite located output in numerical case.')
            json.dumps(candidates, allow_nan=False)  # Validate ALL case diagnostics before committing either outcome.
            rows.extend(candidates)
        except Exception as error:
            # Configuration was validated before the loop. Per-case failures,
            # including numerical-library ValueError, must not erase denominators.
            failed_base = {k: v for k, v in base.items() if k != 'acquisition'}
            for workflow in ('main', 'stage'):
                rows.append(dict(failed_base, workflow=workflow, status='failed', error_type=type(error).__name__, reason=str(error)))
    result = summary(rows)
    result.update(incidents=len(grid), seed=seed, cases=rows,
                  completion_status='failed' if result['failed'] else 'complete',
                  unbalanced=summary([r for r in rows if r['fault'] != 'ABC']),
                  balanced_controls=summary([r for r in rows if r['fault'] == 'ABC']))
    for field in ('workflow', 'noise', 'timing', 'profile', 'fault'):
        groups = {}
        for value in sorted({r[field] for r in rows}):
            subset = [r for r in rows if r[field] == value]
            groups[str(value)] = dict(summary(subset),
                unbalanced=summary([r for r in subset if r['fault'] != 'ABC']),
                balanced_controls=summary([r for r in subset if r['fault'] == 'ABC']))
        result['by_'+field] = groups
    paths = ['scripts/noisy_dsp_validation.py', 'tests/noisy_dsp_records.py', 'tests/source_fault_records.py',
             'tests/source_fault_oracle.py', 'tests/test_noisy_dsp.py', 'tests/test_noisy_dsp_validation.py',
             'tests/test_timestamp_recovery.py', 'tests/test_real_records.py', 'tests/test_workbench.py',
             'tests/test_report.py', 'src/dranalyser/report/render.py', 'src/dranalyser/comtrade/parser.py',
             'src/dranalyser/comtrade/timestamps.py', 'src/dranalyser/dsp/core.py',
             'src/dranalyser/dsp/pipeline.py', 'src/dranalyser/dsp/stage_windows.py',
             'src/dranalyser/faultloc/section_location.py', 'src/dranalyser/faultloc/stage_location.py',
             'src/dranalyser/faultloc/sections.py', 'src/dranalyser/faultloc/ensemble.py']
    result.update(source_sha256_utf8_lf={p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8').encode()).hexdigest() for p in paths},
        runtime=dict(python=sys.version.split()[0], numpy=np.__version__),
        protocol=dict(profiles=list(PROFILES), faults=list(FAULTS), noise=list(NOISE), timing=list(TIMING),
            true_km=75, resistance_ohm=4, sample_rates_hz=[2400, 1200], remote_rotation_rad=1.1,
            waveform_noise='IID real Gaussian samples; sigma=fraction*stronger terminal maximum phase RMS per V/I family over ideal capture.',
            seed_policy='seed+100*profile_index+10*fault_index; matched perturbations across timing modes/noise levels.',
            timing_jitter='DAT encoding jitter <=5us, not physical sample-aperture jitter.',
            clock_skew='R CFG start/trigger +1418s; waveform/local support unchanged; not physical drift recovery.',
            review='Known synthetic one-step identity; no autonomous field pairing.'),
        limits='Bounded synthetic waveform/ASCII parsing experiment, not EMT/instrument reconstruction, '
               'UTC synchronization, drift correction, calibrated confidence, exhaustive coverage or field acceptance.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=854)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose a new evidence path.')
    result = run(args.seed)
    payload = json.dumps(result, indent=2, allow_nan=False)+'\n'
    try:
        with args.output.open('x', encoding='utf-8') as handle:
            handle.write(payload)
    except FileExistsError:
        parser.error('Output already exists; choose a new evidence path.')
    print(json.dumps({k: result[k] for k in ('planned', 'located', 'refused', 'failed')}))
    return 2 if result['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
