"""Secondary waveforms -> integer ASCII COMTRADE -> normal public parsing."""
import datetime as dt

import numpy as np

from dranalyser.comtrade.parser import read_comtrade
from tests.full_record_signals import RATIOS, signals

ADC_MAX = 2**19-1
FULL_SCALE = {'I': 64., 'V': 150.}


def records(directory, *, split, profile, fault, scenario):
    truth = signals(split, profile, fault, scenario)  # Validate before touching output.
    directory.mkdir(parents=True, exist_ok=True)
    pair = {}
    epoch = dt.datetime(2026, 10, 26)
    for end, row in truth.items():
        names = list(row['samples'])
        n, fs = len(row['samples']['IA']), row['fs_true']
        t = np.arange(n)/fs
        cfg = ['Synthetic-full-record,Main-1,2013', '9,6A,3D']
        counts = []
        for i, name in enumerate(names, 1):
            scale = FULL_SCALE[name[0]]/ADC_MAX
            rail = ADC_MAX
            if end == 'S' and name == {'clip_i': 'IA', 'clip_v': 'VA'}.get(scenario):
                rail = max(1, int(round(.3*np.max(abs(row['samples'][name]))/scale)))
            raw = np.clip(np.rint(row['samples'][name]/scale), -rail, rail).astype(np.int64)
            counts.append(raw)
            cfg.append(f'{i},{name},{name[-1]},,{"A" if name[0] == "I" else "V"},{scale:.17g},0,0,{-rail},{rail},{RATIOS[name[0]]},1,S')
        cfg += ['1,PICKUP,0', '2,TRIP,0', '3,CB_OPEN,0']
        declared = scenario != 'gap'
        stated_fs = fs*(1.005 if scenario == 'rate_error' and end == 'R' else 1)
        shift = dt.timedelta(seconds=1418 if scenario == 'clock_skew' and end == 'R' else 0)
        trigger = epoch+shift
        start = trigger-dt.timedelta(seconds=row['pre'])
        cfg += ['50', str(int(declared)), f'{stated_fs if declared else 0},{n}',
                start.strftime('%d/%m/%Y,%H:%M:%S.%f'), trigger.strftime('%d/%m/%Y,%H:%M:%S.%f'),
                'ASCII', '1', '0,+5h30', '4,0']
        path = directory/(end+'.cfg')
        path.write_text('\n'.join(cfg)+'\n', encoding='ascii')
        stamps = np.round(t*1e6)
        if scenario == 'gap' and end == 'R':
            stamps[t >= row['pre']+.2] += 10000
        digital = [t >= row['pre'], t >= row['pre']+.8*row['duration'], t >= row['pre']+row['duration']]
        data = np.column_stack([np.arange(1, n+1), stamps, *counts, *digital])
        np.savetxt(path.with_suffix('.dat'), data, fmt='%d', delimiter=',')
        pair[end] = read_comtrade(str(path), terminal_end=end)
    return pair, truth
