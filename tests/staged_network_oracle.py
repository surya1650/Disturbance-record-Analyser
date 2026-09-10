"""Independent 15-unknown phase-domain branch-equation network oracle.

No synthesis or locator helpers generate the voltages/currents. Each state is
a sinusoidal steady network solution; switches splice states at known physical
times. This is not an EMT/acquisition model and carries no field accuracy claim.
"""
import datetime as dt
import hashlib

import numpy as np

from dranalyser.signals import AnalogMeta, Record

LINE = np.array([[14+42j, 5+12j, 5+12j], [5+12j, 14+42j, 5+12j], [5+12j, 5+12j, 14+42j]])
SOURCE_S = np.array([[4+15j, 1+3j, 1+3j], [1+3j, 4+15j, 1+3j], [1+3j, 1+3j, 4+15j]])
SOURCE_R = np.array([[7+23j, 2+5j, 2+5j], [2+5j, 7+23j, 2+5j], [2+5j, 2+5j, 7+23j]])
ES = 220000/np.sqrt(3)*np.exp(1j*np.array([0, -2*np.pi/3, 2*np.pi/3]))
ER = .99*ES*np.exp(-.1j)


def network(m, phases='', resistance=5.0, opened=False):
    if opened:
        return {'VS': ES.copy(), 'VR': ER.copy(), 'VF': np.zeros(3, complex),
                'IS': np.zeros(3, complex), 'IR': np.zeros(3, complex)}
    # Unknown blocks: VS, VR, VF, IS, IR. Currents positive from each bus
    # into the line. Independent branch Ohm laws plus KCL at the fault node.
    matrix, rhs = np.zeros((15, 15), complex), np.zeros(15, complex)
    unit = np.eye(3)
    matrix[0:3, 0:3], matrix[0:3, 9:12], rhs[0:3] = unit, SOURCE_S, ES
    matrix[3:6, 3:6], matrix[3:6, 12:15], rhs[3:6] = unit, SOURCE_R, ER
    matrix[6:9, 0:3], matrix[6:9, 6:9], matrix[6:9, 9:12] = unit, -unit, -m*LINE
    matrix[9:12, 3:6], matrix[9:12, 6:9], matrix[9:12, 12:15] = unit, -unit, -(1-m)*LINE
    conductance = np.diag([1/resistance if p in phases else 0 for p in 'ABC'])
    matrix[12:15, 6:9], matrix[12:15, 9:12], matrix[12:15, 12:15] = -conductance, unit, unit
    solution = np.linalg.solve(matrix, rhs)
    assert np.max(np.abs(matrix@solution-rhs)) < 1e-7
    return {name: solution[3*i:3*i+3] for i, name in enumerate(('VS', 'VR', 'VF', 'IS', 'IR'))}


def scenario(fs=2400, pre=.12, clock=0, end='S', stage2_m=.32, quiet=True):
    """AG -> ABG -> both breakers open -> reclose onto AG at a different point."""
    schedule = [(0., .22, .32, 'A', False), (.22, .40, stage2_m, 'AB', False),
                (.40, .60, .32, '', quiet), (.60, .90, .73, 'A', False)]
    t = np.arange(round((pre+.9)*fs))/fs
    physical = t-pre
    initial = network(.32)
    arrays = {name: np.tile(initial[name][:, None], (1, len(t))) for name in ('VS', 'VR', 'IS', 'IR')}
    for lo, hi, m, phases, opened in schedule:
        state = network(m, phases, opened=opened)
        for name in arrays:
            arrays[name][:, (physical >= lo) & (physical < hi)] = state[name][:, None]
    analog = {kind+phase: np.sqrt(2)*np.real(arrays[kind+end][i]*np.exp(2j*np.pi*50*physical))
              for kind in ('V', 'I') for i, phase in enumerate('ABC')}
    # Deliberately omit breaker status: the legacy first window spans stages.
    # Command indications are retained as evidence, not physical breaker proof.
    digital = {'TRIP': (((physical >= .38) & (physical < .42)) | (physical >= .85)).astype(int),
               'AR CLOSE': ((physical >= .60) & (physical < .62)).astype(int)}
    start = dt.datetime(2026, 9, 10)+dt.timedelta(seconds=clock)
    digest = hashlib.sha256(b''.join(v.tobytes() for v in analog.values())).hexdigest()
    rec = Record('network-'+end, 'SYNTHETIC NETWORK', 'Main-1', '2013', start,
                 start+dt.timedelta(seconds=pre+.015), fs, 50, t, analog, digital,
                 content_hash=digest, terminal_end=end, time_basis='synthetic')
    rec.analog_meta = {k: AnalogMeta(k, k[0].replace('I', 'A'), 1, 0, 1, 1, 'P', -1e9, 1e9,
                                   normalised=True) for k in analog}
    return rec, schedule


def upload_files():
    """ASCII COMTRADE payloads of the independent synthetic network only."""
    files = []
    for end in ('S', 'R'):
        rec, _ = scenario(end=end, fs=2400 if end == 'S' else 1200,
                          pre=.12 if end == 'S' else .173, clock=0 if end == 'S' else 1418)
        names, digits = list(rec.analog), list(rec.digital)
        cfg = [f'SYNTHETIC-NETWORK-{end},Main-1,2013', f'{len(names)+len(digits)},{len(names)}A,{len(digits)}D']
        cfg += [f'{i},{n},,,{"A" if n.startswith("I") else "V"},0.001,0,0,-1000000000,1000000000,1,1,P'
                for i,n in enumerate(names,1)]
        cfg += [f'{i},{n},,,0' for i,n in enumerate(digits,1)]
        cfg += ['50','1',f'{rec.fs},{rec.n}',rec.start_time.strftime('%d/%m/%Y,%H:%M:%S.%f'),
                rec.trigger_time.strftime('%d/%m/%Y,%H:%M:%S.%f'),'ASCII','1','0,+5h30','F,0']
        dat = [','.join(map(str, [i+1,round(t*1e6)]+[round(rec.analog[n][i]*1000) for n in names]+
                           [int(rec.digital[n][i]) for n in digits])) for i,t in enumerate(rec.t)]
        for ext,content in [('cfg',cfg),('dat',dat)]:
            files.append(('files',(f'{end}/event.{ext}', ('\n'.join(content)+'\n').encode(), 'application/octet-stream')))
    return files
