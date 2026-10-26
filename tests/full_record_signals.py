"""Independent phase-network and CT signals, in secondary A/V, before ADC."""
import numpy as np

from tests.ct_quality_oracle import KNEE, simulate
from tests.source_fault_oracle import solve, source_pair

SECTIONS = [(40, .03+.25j, .4+1.4j), (60, .3+.7j, .1+1j)]
FAULTS = ('AG', 'BC', 'ABG', 'ABC')
SCENARIOS = ('clean', 'white_0.001', 'white_0.01', 'colored', 'quantized',
             'ct_single', 'ct_multi', 'ct_noisy', 'clip_i', 'clip_v', 'dropout',
             'spike', 'harmonic', 'alias_harmonic', 'alias_fundamental', 'gain_i',
             'gain_v', 'polarity', 'short', 'gap', 'rate_error', 'drift', 'clock_skew')
SPLITS = {
    'development': dict(freq=49, rates=(2400, 1600), pre=(.14, .181), duration=.36,
                        rotation=.63, dc=.7, tau=.055, burden=.6, bias=.3, seed=2854,
                        profiles=('baseline', 'weak_R_100', 'voltage_unbalance')),
    'validation': dict(freq=51, rates=(3200, 2000), pre=(.16, .193), duration=.39,
                       rotation=1.37, dc=1.2, tau=.085, burden=1.3, bias=-.45, seed=3854,
                       profiles=('baseline', 'weak_R_10000', 'phase_impedance'))}
RATIOS = {'I': 1000, 'V': 2000}


def validate(split, profile, fault, scenario):
    if (split not in SPLITS or profile not in SPLITS[split]['profiles'] or
            fault not in FAULTS or scenario not in SCENARIOS):
        raise ValueError('Invalid full-record experiment configuration.')


def signals(split, profile, fault, scenario):
    """State splices and optional CT; not EMT or a manufacturer instrument model."""
    validate(split, profile, fault, scenario)
    spec = SPLITS[split]
    sources = source_pair(profile)
    quiet = solve(SECTIONS, 75, 'NONE', sources=sources)
    active = solve(SECTIONS, 75, fault, 4, sources=sources)
    out = {}
    duration = .06 if scenario == 'short' else spec['duration']
    for index, end in enumerate(('S', 'R')):
        fs, pre, freq = spec['rates'][index], spec['pre'][index], spec['freq']
        t = np.arange(round((pre+duration+.06)*fs))/fs
        physical = t-pre
        angle = 2*np.pi*(freq*physical+(.5*physical**2 if scenario == 'drift' else 0))
        angle += spec['rotation'] if end == 'R' else 0
        ideal, ct_only, flux, residual = {}, {}, {}, 0.
        ct_names = (['IA'] if scenario == 'ct_single' and end == 'S' else
                    ['IA', 'IB', 'IC'] if scenario in ('ct_multi', 'ct_noisy') else [])
        for kind in ('I', 'V'):
            for phase, name in enumerate(kind+p for p in 'ABC'):
                ph = np.where((physical >= 0) & (physical < duration), active[kind+end][phase], quiet[kind+end][phase])
                wave = np.sqrt(2)*np.real(ph*np.exp(1j*angle))/RATIOS[kind]
                if kind == 'I':
                    wave[physical >= duration] = 0
                    if scenario.startswith('ct_'):
                        magnitude = spec['dc']*np.sqrt(2)*abs(active[kind+end][phase])/RATIOS[kind]
                        wave += magnitude*np.sign(active[kind+end][phase].real)*np.exp(-np.maximum(physical, 0)/spec['tau'])*((physical >= 0) & (physical < duration))
                ideal[name] = wave
                ct_only[name] = wave.copy()
                if name in ct_names:
                    model = simulate(wave, fs, burden=spec['burden'], initial_flux=spec['bias']*KNEE)
                    ct_only[name] = model['secondary']
                    residual = max(residual, float(np.max(abs(wave-model['secondary']-model['excitation']))))
                    flux[name] = float(np.max(abs(model['flux']))/KNEE)
        lo = int(np.ceil((pre+1.5/freq)*fs))
        hi = int(np.floor((pre+duration-.5/freq)*fs))
        out[end] = dict(ideal=ideal, ct_only=ct_only, samples={n: v.copy() for n, v in ct_only.items()},
                        fs_true=fs, freq_true=freq, pre=pre, duration=duration,
                        window_indices=[lo, hi], ct_channels=ct_names,
                        ct_balance_max_residual=residual, ct_peak_flux_knee=flux)
    scales = {kind: max(np.sqrt(np.mean(v**2)) for row in out.values() for n, v in row['ideal'].items() if n[0] == kind)
              for kind in ('I', 'V')}
    rng = np.random.default_rng(spec['seed']+100*spec['profiles'].index(profile)+10*FAULTS.index(fault))
    for end, row in out.items():
        row['family_scale'] = dict(scales)
        for name, wave in row['samples'].items():
            noise = rng.normal(size=len(wave))
            if scenario.startswith('white_') or scenario == 'ct_noisy':
                wave += (float(scenario.split('_')[1]) if scenario.startswith('white_') else .01)*scales[name[0]]*noise
            elif scenario == 'colored':
                filtered = np.convolve(noise, np.ones(5)/5, mode='same')
                wave += .01*scales[name[0]]*filtered/np.sqrt(np.mean(filtered**2))
            elif scenario == 'quantized':
                step = .01*scales[name[0]]
                wave[:] = np.round(wave/step)*step
        if end == 'S':
            t = np.arange(len(row['samples']['IA']))/row['fs_true']
            current = row['samples']['IA']
            middle = int(round((row['pre']+.15)*row['fs_true']))
            if scenario == 'dropout':
                current[middle:middle+round(.25*row['fs_true']/row['freq_true'])] = 0
            elif scenario == 'spike':
                current[middle] += 3*scales['I']
            elif scenario in ('harmonic', 'alias_harmonic', 'alias_fundamental'):
                frequency = 3*row['freq_true'] if scenario == 'harmonic' else row['fs_true']-(3 if scenario == 'alias_harmonic' else 1)*row['freq_true']
                current += .15*scales['I']*np.sin(2*np.pi*frequency*t)
            elif scenario in ('gain_i', 'gain_v'):
                for name in row['samples']:
                    if name[0] == ('I' if scenario == 'gain_i' else 'V'):
                        row['samples'][name] *= 1.2
        elif scenario == 'polarity':
            row['samples']['IA'] *= -1
    return out
