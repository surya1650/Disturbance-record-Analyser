"""Sinusoidal state-splice records from the independent phase nodal network.

No production synthesis or phasor substitution; not EMT or instrument modeling.
"""
import datetime as dt
import hashlib

import numpy as np

from dranalyser.signals import AnalogMeta, Record
from tests.source_fault_oracle import solve, source_pair


def records(sections, km, fault, resistance=4, profile='baseline', rotation=1.1):
    sources = source_pair(profile)
    quiet = solve(sections, km, 'NONE', sources=sources)
    active = solve(sections, km, fault, resistance, sources=sources)
    out = {}
    for end, fs, pre in [('S', 2400, .12), ('R', 1200, .173)]:
        t = np.arange(round((pre+.5)*fs))/fs
        physical = t-pre
        analog = {}
        for kind in ('V', 'I'):
            ph = np.where(physical[None, :] < 0, quiet[kind+end][:, None], active[kind+end][:, None])
            wave = np.sqrt(2)*np.real(ph*np.exp(1j*(2*np.pi*50*physical+(rotation if end == 'R' else 0))))
            analog.update({kind+p: wave[i] for i, p in enumerate('ABC')})
        epoch = dt.datetime(2026, 10, 23)
        digest = hashlib.sha256(b''.join(v.tobytes() for v in analog.values())).hexdigest()
        rec = Record('source-fault-'+end, 'SYNTHETIC', 'Main-1', '2013',
                     epoch-dt.timedelta(seconds=pre), epoch, fs, 50, t, analog, {},
                     content_hash=digest, terminal_end=end, time_basis='synthetic')
        rec.analog_meta = {k: AnalogMeta(k, 'A' if k[0] == 'I' else 'V', 1, 0, 1, 1, 'P', -1e9, 1e9,
                                       normalised=True) for k in analog}
        out[end] = rec
    return out
