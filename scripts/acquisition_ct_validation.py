"""Independent CT/noise study; a passing research candidate never clears gates."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'src'))

from scripts.acquisition_quality_candidate import POLICY, assess  # noqa: E402
from tests.ct_quality_oracle import KNEE, simulate  # noqa: E402
from dranalyser.dsp.detect import detect_saturation  # noqa: E402


def ct_grid(split):
    if split == 'development':
        return itertools.product([50], [1000, 2400], [0, .7], [0, 1], [.04], [.2, 1, 2], [0, .7])
    return itertools.product([47, 53], [1200, 4800], [.31, 1.23], [.4, 1.4], [.065], [.35, .8, 1.6], [-.6, .4])


def projection(samples, fs, freq, start):
    """Independent trapezoidal quadrature on complete cycles, interpolated in time."""
    cycles = int((len(samples)-1-start)*freq/fs)
    t = (start/fs)+np.linspace(0, cycles/freq, cycles*256+1)
    u = np.interp(t, np.arange(len(samples))/fs, samples)
    return 2/(t[-1]-t[0])*np.trapezoid(u*np.exp(-2j*np.pi*freq*t), t)


def score(samples, fs, freq):
    start = int(np.ceil(1.5*fs/freq))
    candidate = assess(samples[start:], fs, freq)
    legacy = detect_saturation({'IA': samples}, fs, freq, start, len(samples))
    return dict(status='evaluated', candidate=candidate, legacy_saturation=legacy.detected,
                legacy_severity=legacy.severity)


def control(kind, split):
    fs, freq = (2400, 50) if split == 'development' else (4800, 53)
    t = np.arange(round(.3*fs))/fs
    u = np.sqrt(2)*np.sin(2*np.pi*freq*t+.31)
    noise = np.random.default_rng(854 if split == 'development' else 1854).normal(size=len(u))
    if kind.startswith('white_'):
        u += float(kind.split('_')[1])*noise
    elif kind == 'colored':
        filtered = np.convolve(noise, np.ones(5)/5, mode='same')
        u += .01*filtered/np.sqrt(np.mean(filtered**2))
    elif kind == 'quantized':
        u = np.round(u/.01)*.01
    elif kind == 'harmonic':
        u += .1*np.sqrt(2)*np.sin(6*np.pi*freq*t)
    elif kind == 'clipped':
        u = np.clip(u, -.6, .6)
    elif kind == 'dropout':
        begin = round(.15*fs)
        u[begin:begin+round(.25*fs/freq)] = 0
    return score(u, fs, freq)


def summary(rows):
    evaluated = [r for r in rows if r['status'] == 'evaluated']
    harmful = [r for r in evaluated if r['kind'] == 'ct' and r['fundamental_error'] > .05]
    def passes(values):
        return sum(r['candidate']['status'] == 'candidate_pass' for r in values)
    unsafe_controls = [r for r in evaluated if r['kind'] in ('harmonic', 'clipped', 'dropout', 'white_0.05')]
    return dict(planned=len(rows), evaluated=len(evaluated), failed=len(rows)-len(evaluated),
                candidate_pass=passes(evaluated), harmful_ct=len(harmful), harmful_ct_pass=passes(harmful),
                unsafe_controls=len(unsafe_controls), unsafe_control_pass=passes(unsafe_controls),
                legacy_flags=sum(r['legacy_saturation'] for r in evaluated))


def run():
    rows = []
    for split in ('development', 'holdout'):
        for incident, params in enumerate(ct_grid(split)):
            freq, fs, phase, dc, tau, burden, bias = params
            for noise in (0, .01):
                base = dict(split=split, kind='ct', incident=incident, frequency_hz=freq, fs=fs,
                            phase_rad=phase, dc=dc, decay_s=tau, burden_ohm=burden, initial_flux_knee=bias, noise=noise)
                try:
                    t = np.arange(round(.3*fs))/fs
                    ideal = np.sqrt(2)*np.sin(2*np.pi*freq*t+phase)+dc*np.exp(-t/tau)
                    ct = simulate(ideal, fs, burden=burden, initial_flux=bias*KNEE)
                    start = int(np.ceil(1.5*fs/freq))
                    expected = projection(ideal, fs, freq, start)
                    error = abs(projection(ct['secondary'], fs, freq, start)-expected)/abs(expected)
                    rng = np.random.default_rng((854 if split == 'development' else 1854)+incident)
                    measured = ct['secondary']+noise*rng.normal(size=len(t))
                    row = dict(base, **score(measured, fs, freq), fundamental_error=float(error),
                               crossed_knee=bool(np.max(abs(ct['flux'])) > KNEE),
                               maximum_flux_knee=float(np.max(abs(ct['flux']))/KNEE))
                    json.dumps(row, allow_nan=False)
                except Exception as error:
                    row = dict(base, status='failed', error_type=type(error).__name__, reason=str(error))
                rows.append(row)
        for kind in ('clean', 'white_0.001', 'white_0.01', 'white_0.05', 'colored', 'quantized', 'harmonic', 'clipped', 'dropout'):
            base = dict(split=split, kind=kind)
            try:
                row = dict(base, **control(kind, split))
                json.dumps(row, allow_nan=False)
            except Exception as error:
                row = dict(base, status='failed', error_type=type(error).__name__, reason=str(error))
            rows.append(row)
    splits = {split: summary([r for r in rows if r['split'] == split]) for split in ('development', 'holdout')}
    overall, holdout = summary(rows), splits['holdout']
    gate = ('failed' if overall['failed'] or not holdout['harmful_ct'] or
            holdout['harmful_ct_pass'] or holdout['unsafe_control_pass'] else 'passed_bounded_study')
    paths = ['scripts/acquisition_ct_validation.py', 'scripts/acquisition_quality_candidate.py',
             'tests/ct_quality_oracle.py', 'tests/test_ct_quality_oracle.py', 'tests/test_acquisition_ct_validation.py',
             'src/dranalyser/dsp/detect.py', 'docs/superpowers/specs/2026-10-26-acquisition-ct-quality.md']
    return dict(overall, splits=splits, cases=rows, adoption_gate=gate, production_gates_changed=False,
                policy=POLICY, harmful_current_error_threshold=.05,
                noise_scale='secondary-referred A RMS; nominal primary 1000 A, ratio 1000:1',
                truth='Error in independent complete-cycle complex fundamental quadrature, before added measurement noise.',
                limits='Toy memoryless CT excitation, resistive burden, initial flux bias; no hysteresis, remanence validation, '
                       'manufacturer model, field acceptance or production authorization. Disjoint holdout; no tuning.',
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
    print(json.dumps({k: v for k, v in result.items() if k in ('planned', 'failed', 'adoption_gate', 'splits')}))
    return 2 if result['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
