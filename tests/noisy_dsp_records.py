"""Independent nodal waveforms -> noisy ASCII COMTRADE -> public parser.

Timestamp jitter is encoding noise, not a physical sampling-aperture model.
"""
import datetime as dt

import numpy as np

from dranalyser.comtrade.parser import read_comtrade
from tests.source_fault_records import records as ideal_records
from tests.test_source_fault_oracle import SECTIONS

TIMING = ('declared', 'rounded', 'bounded_jitter', 'clock_skew', 'gap')


def records(directory, *, fault='AG', profile='baseline', noise=0, timing='declared', seed=854):
    if timing not in TIMING or not np.isfinite(noise) or noise < 0:
        raise ValueError('Unknown timing mode or invalid waveform noise level.')
    directory.mkdir(parents=True, exist_ok=True)
    ideal = ideal_records(SECTIONS, 75, fault, profile=profile)
    scales = {kind: max(np.sqrt(np.mean(r.analog[kind+p]**2)) for r in ideal.values() for p in 'ABC')
              for kind in ('V', 'I')}
    rng, jitter_rng = np.random.default_rng(seed), np.random.default_rng(seed+1000000)
    out = {}
    for end, rec in ideal.items():
        channels = list(rec.analog)
        waves = {name: rec.analog[name]+noise*scales[name[0]]*rng.normal(size=rec.n) for name in channels}
        declared = timing in ('declared', 'clock_skew')
        stamps = np.round(rec.t*1e6)
        if timing == 'bounded_jitter':
            stamps = np.round(rec.t*1e6+jitter_rng.uniform(-5, 5, rec.n))
        if timing == 'gap' and end == 'R':
            stamps[rec.n//2:] += 10000
        shift = dt.timedelta(seconds=1418 if timing == 'clock_skew' and end == 'R' else 0)
        dates = [(rec.start_time+shift).strftime('%d/%m/%Y,%H:%M:%S.%f'),
                 (rec.trigger_time+shift).strftime('%d/%m/%Y,%H:%M:%S.%f')]
        cfg = ['Synthetic-noisy,Main-1,2013', '6,6A,0D']
        cfg += [f'{i},{name},{name[-1]},,{"A" if name[0] == "I" else "V"},1,0,0,-1e9,1e9,1,1,P'
                for i, name in enumerate(channels, 1)]
        cfg += ['50', str(int(declared)), f'{rec.fs if declared else 0},{rec.n}', *dates,
                'ASCII', '1', '0,+5h30', '4,0']
        path = directory/(end+'.cfg')
        path.write_text('\n'.join(cfg)+'\n', encoding='ascii')
        rows = np.column_stack([np.arange(1, rec.n+1), np.zeros(rec.n) if declared else stamps,
                                *[waves[name] for name in channels]])
        np.savetxt(path.with_suffix('.dat'), rows, fmt='%.17g', delimiter=',')
        out[end] = read_comtrade(str(path), terminal_end=end)
    return out
