"""Frozen direct circuit sums and independent phase nodal states; no locator imports."""
import hashlib
import itertools
import json

import numpy as np

from tests.section_network_oracle import negative, solve

SEEDS = (91631, 92743)
POSITIONS = (0, .137, .37, .731, 1)
PROFILES = ('baseline', 'weakS', 'weakR', 'bothWeak')
ROTATIONS = (0, 1.713)
CAPS = ('exact', 'bounded', 'wide')
MODELS = {'uniform': [(1, 10+39j)],
          'sections': [(.23, 1+8j), (.61, 7+12j), (1, 2+19j)]}


def case_grid():
    direct = [dict(kind='direct', seed=s, m=m, model=model, profile=p, rotation=r, caps=c)
              for s, m, model, p, r, c in itertools.product(SEEDS, POSITIONS, MODELS, PROFILES, ROTATIONS, CAPS)]
    violated = [dict(kind='violated', seed=s, m=.417, model='sections', profile=p,
                     rotation=.817, caps='exact', defect=d)
                for s, p, d in itertools.product(SEEDS, PROFILES, ('gain', 'polarity'))]
    nodal = [dict(kind='nodal', m=m, phase=p, reverse=reverse, rotation=r, model='sections', caps='exact')
             for reverse, p, m, r in itertools.product((False, True), range(3), (.01, .23, .42, .61, .99), ROTATIONS)]
    return direct+violated+nodal


def make_case(config):
    sections = MODELS[config['model']]
    m, start, left = config['m'], 0.0, 0j
    lengths = []
    for end, impedance in sections:
        length = end-start
        left += impedance*max(0, min(1, (m-start)/length))
        lengths.append((100*length, impedance/(100*length), 3*impedance/(100*length)))
        start = end
    rotation = np.exp(1j*config['rotation'])
    key = json.dumps(config, sort_keys=True).encode()
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest()[:8], 'big'))
    supports = []
    kcl_residual = None
    if config['kind'] == 'nodal':
        state = solve(lengths, 100*m, phase=config['phase'], resistance=7.3,
                      reverse_sources=config['reverse'])
        truth = [negative(state[k]) for k in ('VS', 'IS', 'VR', 'IR')]
        truth[2:] = [v*rotation for v in truth[2:]]
        supports.append(dict(truth=truth, measured=truth.copy(), caps=[0.0]*4))
        kcl_residual = state['residual']
    else:
        for _ in range(3):
            f = 20+15j+3*(rng.normal()+1j*rng.normal())
            is_, ir = 2-1j+.2*(rng.normal()+1j*rng.normal()), 3+.5j+.2*(rng.normal()+1j*rng.normal())
            if config['profile'] in ('weakS', 'bothWeak'):
                is_ *= 1e-6
            if config['profile'] in ('weakR', 'bothWeak'):
                ir *= 1e-6
            truth = [f+left*is_, is_, (f+(sum(z for _, z in sections)-left)*ir)*rotation, ir*rotation]
            caps = {'exact': [0.0]*4, 'bounded': [.03, .002, .03, .002], 'wide': [1000, 100, 1000, 100]}[config['caps']]
            errors = np.array(caps)*rng.uniform(0, .95, 4)*np.exp(1j*rng.uniform(-np.pi, np.pi, 4))
            measured = [complex(t+e) for t, e in zip(truth, errors, strict=True)]
            if config['kind'] == 'violated':
                measured[1] *= 1.17 if config['defect'] == 'gain' else -1
            supports.append(dict(truth=truth, measured=measured, caps=caps))
    covered = all(abs(v-t) <= c*(1+1e-12)+1e-12 for s in supports
                  for v, t, c in zip(s['measured'], s['truth'], s['caps'], strict=True))
    return dict(sections=sections, m=m, left_impedance=left, supports=supports,
                caps_cover_truth=covered, kcl_residual=kcl_residual)
