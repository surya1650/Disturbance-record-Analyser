"""Disjoint independent uniform-network states, toy CT and integer acquisition."""
import importlib.util
from pathlib import Path

import numpy as np

from tests.ct_quality_oracle import KNEE, simulate
from tests.source_fault_oracle import FAULTS, solve, source_pair

SECTIONS = [(120, .055+.33j, .22+.91j)]
SPLITS = {
    'development': dict(freq=47.5, rates=(3000, 1800), pre=(.155, .207), duration=.34,
        rotation=.79, dc=.8, tau=.063, burden=.8, bias=.2, seed=6854, km=37, rf=3,
        profiles=('baseline', 'weak_R_100')),
    'validation': dict(freq=51.5, rates=(3600, 2200), pre=(.175, .223), duration=.37,
        rotation=1.41, dc=1.1, tau=.079, burden=1.1, bias=-.25, seed=7854, km=83, rf=7,
        profiles=('baseline', 'weak_S_10000'))}
SCENARIOS = ('clean', 'white_small', 'colored_small', 'ct_single', 'ct_all', 'ct_noise',
             'clip_i', 'clip_v', 'gain_i', 'gain_v', 'polarity', 'alias', 'gap', 'clock_skew')
RATIOS = {'I': 1000, 'V': 2000}


def validate(split, profile, fault, scenario):
    if (split not in SPLITS or profile not in SPLITS[split]['profiles'] or
            fault not in FAULTS or scenario not in SCENARIOS):
        raise ValueError('Invalid scalar-observability source configuration.')


def signals(split, profile, fault, scenario):
    validate(split, profile, fault, scenario)
    spec = SPLITS[split]
    sources = source_pair(profile)
    quiet = solve(SECTIONS, spec['km'], 'NONE', sources=sources)
    active = solve(SECTIONS, spec['km'], fault, spec['rf'], sources=sources)
    out = {}
    for index, end in enumerate(('S', 'R')):
        fs, pre, freq = spec['rates'][index], spec['pre'][index], spec['freq']
        physical = np.arange(round((pre+spec['duration']+.06)*fs))/fs-pre
        active_mask = (physical >= 0) & (physical < spec['duration'])
        phase = 2*np.pi*freq*physical+(spec['rotation'] if end == 'R' else 0)
        ideal, ct_only, flux, residual = {}, {}, {}, 0.
        ct_names = (['IA'] if scenario == 'ct_single' and end == 'S' else
                    ['IA', 'IB', 'IC'] if scenario in ('ct_all', 'ct_noise') and end == 'S' else [])
        for kind in ('I', 'V'):
            for p, name in enumerate(kind+c for c in 'ABC'):
                ph = np.where(active_mask, active[kind+end][p], quiet[kind+end][p])
                wave = np.sqrt(2)*np.real(ph*np.exp(1j*phase))/RATIOS[kind]
                if kind == 'I':
                    wave[physical >= spec['duration']] = 0
                    if scenario.startswith('ct_'):
                        dc = spec['dc']*np.sqrt(2)*abs(active[kind+end][p])/RATIOS[kind]
                        wave += dc*np.sign(active[kind+end][p].real)*np.exp(-np.maximum(physical, 0)/spec['tau'])*active_mask
                ideal[name], ct_only[name] = wave, wave.copy()
                if name in ct_names:
                    model = simulate(wave, fs, burden=spec['burden'], initial_flux=spec['bias']*KNEE)
                    ct_only[name] = model['secondary']
                    flux[name] = float(np.max(abs(model['flux']))/KNEE)
                    residual = max(residual, float(np.max(abs(wave-model['secondary']-model['excitation']))))
        out[end] = dict(ideal=ideal, ct_only=ct_only, samples={n: x.copy() for n, x in ct_only.items()},
            fs_true=fs, freq_true=freq, pre=pre, duration=spec['duration'],
            window_indices=[int(np.ceil((pre+1.5/freq)*fs)), int(np.floor((pre+spec['duration']-.5/freq)*fs))],
            ct_channels=ct_names, ct_balance_max_residual=residual, ct_peak_flux_knee=flux)
    scales = {k: max(np.sqrt(np.mean(v*v)) for row in out.values() for n, v in row['ideal'].items() if n[0] == k)
              for k in ('I', 'V')}
    rng = np.random.default_rng(spec['seed']+100*spec['profiles'].index(profile)+10*FAULTS.index(fault))
    for end, row in out.items():
        for name, wave in row['samples'].items():
            noise = rng.normal(size=len(wave))
            if scenario in ('white_small', 'ct_noise'):
                wave += (.0005 if scenario == 'white_small' else .002)*scales[name[0]]*noise
            elif scenario == 'colored_small':
                colored = np.convolve(noise, np.ones(7)/7, mode='same')
                wave += .002*scales[name[0]]*colored/np.sqrt(np.mean(colored*colored))
            if end == 'S' and scenario in ('gain_i', 'gain_v') and name[0] == ('I' if scenario == 'gain_i' else 'V'):
                wave *= 1.15 if scenario == 'gain_i' else 1.12
        if end == 'S' and scenario == 'polarity':
            row['samples']['IA'] *= -1
        elif end == 'S' and scenario == 'alias':
            t = np.arange(len(row['samples']['IA']))/row['fs_true']
            row['samples']['IA'] += .12*scales['I']*np.sin(2*np.pi*(row['fs_true']-row['freq_true'])*t)
    return out


def records(directory, *, split, profile, fault, scenario):
    validate(split, profile, fault, scenario)
    path = Path(__file__).with_name('full_record_acquisition.py')
    spec = importlib.util.spec_from_file_location('scalar_independent_writer', path)
    writer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(writer)
    writer.signals = signals
    return writer.records(directory, split=split, profile=profile, fault=fault, scenario=scenario)
