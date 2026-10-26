"""Independent synthetic metrology signals, not a line/fault-location network."""
import datetime as dt

import numpy as np

from dranalyser.comtrade.parser import read_comtrade

SPLITS = {'development': dict(freq=48, fs=3500, pre=.14, angle=.37, seed=4854),
          'validation': dict(freq=52, fs=2600, pre=.17, angle=.91, seed=5854)}
I2_VALUES = (0, .1, 10, 100)
SCENARIOS = ('quantization', 'uniform_small', 'uniform_large', 'colored_small', 'colored_large',
             'square_small', 'square_large', 'gain', 'polarity', 'alias')
ADC_MAX = 2**19-1


def validate(split, i2, scenario):
    if split not in SPLITS or i2 not in I2_VALUES or isinstance(i2, bool) or scenario not in SCENARIOS:
        raise ValueError('Invalid sequence-budget record configuration.')


def records(directory, *, split, i2, scenario):
    validate(split, i2, scenario)
    spec = SPLITS[split]
    fs, freq, pre = spec['fs'], spec['freq'], spec['pre']
    t = np.arange(round((pre+.36+.06)*fs))/fs
    physical = t-pre
    a = np.exp(2j*np.pi/3)
    positive, negative = np.array([1, a*a, a]), np.array([1, a, a*a])
    currents = np.where(physical[None, :] < 0, 100*positive[:, None],
        (1000*positive+i2*np.exp(1j*spec['angle'])*negative)[:, None])
    current_waves = np.sqrt(2)*np.real(currents*np.exp(2j*np.pi*freq*physical))
    current_waves[:, physical >= .36] = 0
    voltage_waves = np.sqrt(2)*220000/np.sqrt(3)*np.real(positive[:, None]*np.exp(2j*np.pi*freq*physical))
    ideal = {kind+p: waves[index] for kind, waves in [('I', current_waves), ('V', voltage_waves)]
             for index, p in enumerate('ABC')}
    measured = {name: value.copy() for name, value in ideal.items()}
    level = .001 if scenario.endswith('_small') else .01 if scenario.endswith('_large') else 0
    amplitude_cap = level*(1000+i2)
    rng = np.random.default_rng(spec['seed']+100*I2_VALUES.index(i2))
    for index, name in enumerate(('IA', 'IB', 'IC')):
        noise = rng.uniform(-1, 1, len(t))
        if scenario.startswith('colored'):
            noise = np.convolve(noise, np.ones(5)/5, mode='same')
        elif scenario.startswith('square'):
            noise = np.sign(np.cos(2*np.pi*freq*t+.13*index))
        measured[name] += amplitude_cap*noise
        if scenario == 'gain':
            measured[name] *= 1.2
    if scenario == 'polarity':
        measured['IA'] *= -1
    elif scenario == 'alias':
        measured['IA'] += .15*(1000+i2)*np.sin(2*np.pi*(fs-freq)*t)
    directory.mkdir(parents=True, exist_ok=True)
    cfg = ['Synthetic-metrology,Main-1,2013', '8,6A,2D']
    raw, caps = [], {}
    for index, name in enumerate(ideal, 1):
        ratio, full_scale = (1000, 64) if name[0] == 'I' else (2000, 150)
        step = full_scale/ADC_MAX
        counts = np.clip(np.rint(measured[name]/ratio/step), -ADC_MAX, ADC_MAX).astype(np.int64)
        raw.append(counts)
        if name[0] == 'I':
            caps[name] = amplitude_cap+.5*step*ratio
        cfg.append(f'{index},{name},{name[-1]},,{"A" if name[0] == "I" else "V"},{step:.17g},0,0,{-ADC_MAX},{ADC_MAX},{ratio},1,S')
    epoch = dt.datetime(2026, 10, 27)
    cfg += ['1,TRIP,0', '2,CB_OPEN,0', '50', '1', f'{fs},{len(t)}',
            (epoch-dt.timedelta(seconds=pre)).strftime('%d/%m/%Y,%H:%M:%S.%f'),
            epoch.strftime('%d/%m/%Y,%H:%M:%S.%f'), 'ASCII', '1', '0,+5h30', '4,0']
    path = directory/'budget.cfg'
    path.write_text('\n'.join(cfg)+'\n', encoding='ascii')
    data = np.column_stack([np.arange(1, len(t)+1), np.round(t*1e6), *raw,
                            physical >= .30, physical >= .36])
    np.savetxt(path.with_suffix('.dat'), data, fmt='%d', delimiter=',')
    truth = dict(true_frequency_hz=freq, physical_i2_rms_primary_a=i2, pre=pre,
                 negative_phase_rad=spec['angle'], window_s=[pre+1.5/freq, pre+.36-.5/freq],
                 sample_noise_cap_primary_a=amplitude_cap,
                 provenance='Synthetic hard sample cap + unclipped ADC half-step; excludes unmodeled bias/frequency/kernel/clock error.')
    return read_comtrade(str(path)), ideal, caps, truth
