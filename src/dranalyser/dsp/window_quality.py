"""Conservative changes between settled phasor blocks; no event identity claim."""
import numpy as np

NAMES = ('IA', 'IB', 'IC', 'VA', 'VB', 'VC')
POLICY = {'minimum_changed_channels': 2, 'relative_change': .20, 'plateau_tolerance': .08}


def window_transition(an, start=None, end=None):
    rec, ps = an.record, an.ps
    start = an.window.t_start if start is None else start
    end = an.window.t_end if end is None else end
    out = {'status': 'not assessed', 'reason': '', 'policy': dict(POLICY), 'transitions': []}
    if (rec.nrates > 1 or not np.isfinite(rec.fs) or not np.isfinite(an.freq) or rec.fs <= 0 or an.freq <= 0 or
            not np.allclose(np.diff(rec.t), 1/rec.fs, rtol=.01, atol=1e-7) or
            any(n not in ps.phasors for n in NAMES)):
        out['reason'] = 'Uniform grid and six phase phasors required for transition screening.'
        return out
    ids = ps.window_indices(start, end)
    cycle = int(round(rec.fs/an.freq))
    if cycle < 4 or len(ids) < 5*cycle:
        out['reason'] = 'Fewer than five complete phasor blocks; transition screen inconclusive.'
        return out
    ids = ids[:len(ids)//cycle*cycle]
    values = np.array([ps.phasors[n][ids] for n in NAMES]).reshape(6, -1, cycle)
    if not np.all(np.isfinite(values)):
        out['reason'] = 'Nonfinite phasors; transition screen unavailable.'
        return out
    blocks = np.median(values.real, axis=2)+1j*np.median(values.imag, axis=2)
    floor = np.array([max(.2*abs(an.ref.get(n, 0j)), 1e-6) for n in NAMES])
    for split in range(2, blocks.shape[1]-2):
        before, after = blocks[:, split-2:split], blocks[:, split+1:split+3]
        a, b = before.mean(axis=1), after.mean(axis=1)
        scale = np.maximum(np.maximum(abs(a), abs(b)), floor)
        changed = abs(a-b)/scale > POLICY['relative_change']
        settled = (abs(before[:, 0]-before[:, 1])/scale < POLICY['plateau_tolerance']) & (
            abs(after[:, 0]-after[:, 1])/scale < POLICY['plateau_tolerance'])
        channels = [n for n, good in zip(NAMES, changed & settled, strict=True) if good]
        if len(channels) >= POLICY['minimum_changed_channels']:
            out['transitions'].append({'local_support_s': [float(ps.t[ids[(split-1)*cycle]]),
                                                           float(ps.t[ids[(split+2)*cycle-1]])],
                                       'channels': channels})
    out.update(status='transition detected' if out['transitions'] else 'no transition detected',
               reason='Different settled phasor states; a mixed-window location is withheld.' if out['transitions'] else
                      'No supported plateau change found; this does not establish physical stage identity.')
    return out
