"""Frozen research screen. Outputs never authorize production fault location."""
import numpy as np

POLICY = dict(residual_rms=.02, harmonic_rms=.03, peak_residual=.08,
              minimum_cycles=4, minimum_samples_per_cycle=16,
              dc_time_constants_s=[.01, .03, .1])


def assess(samples, fs, freq):
    """Separate fitted coherent harmonics from unmodeled noise/transients.

    Neither component establishes magnetic CT saturation. No frequency recovery,
    acquisition timing validation or uncertainty calibration is performed here.
    """
    out = dict(status='unsupported', authorizes_location=False, policy=dict(POLICY))
    u = np.asarray(samples, dtype=float)
    if (u.ndim != 1 or u.size < 8 or not np.all(np.isfinite(u)) or
            not np.isfinite(fs) or not np.isfinite(freq) or fs <= 0 or freq <= 0):
        return out
    spc = fs/freq
    if not np.isfinite(spc) or spc < POLICY['minimum_samples_per_cycle'] or u.size/spc < POLICY['minimum_cycles']:
        return out
    scale = float(np.max(abs(u)))
    if scale < 1e-9:
        return out
    t = np.arange(u.size)/fs
    angle = 2*np.pi*(np.arange(u.size)/spc)
    basis = [np.ones(u.size)]
    for harmonic in range(1, 6):
        basis.extend([np.sin(harmonic*angle), np.cos(harmonic*angle)])
    basis.extend(np.exp(-t/tau) for tau in POLICY['dc_time_constants_s'])
    design = np.array(basis).T
    coefficients = np.linalg.lstsq(design, u/scale, rcond=None)[0]
    fundamental = float(np.hypot(*coefficients[1:3])/np.sqrt(2))
    if fundamental < 1e-5:
        return out
    residual = u/scale-design@coefficients
    values = dict(residual_rms=float(np.sqrt(np.mean(residual**2))/fundamental),
                  harmonic_rms=float(np.linalg.norm(coefficients[3:11])/np.sqrt(2)/fundamental),
                  peak_residual=float(np.max(abs(residual))/fundamental))
    if not all(np.isfinite(v) for v in values.values()):
        return out
    status = ('distortion' if values['harmonic_rms'] > POLICY['harmonic_rms'] else
              'noise_or_transient' if any(values[k] > POLICY[k] for k in ('residual_rms', 'peak_residual'))
              else 'candidate_pass')
    return dict(out, status=status, **values)
