"""Independent, secondary-referred CT with resistive burden and odd excitation.

u = secondary + excitation(flux); dflux/dt = burden * secondary.
Flux is linkage in V s. Initial bias is not hysteretic remanence. Piecewise
excitation is a toy curve, not a manufacturer model. No production imports.
"""
import numpy as np

KNEE = .03
L_LINEAR = 10.
L_SATURATED = .0005


def excitation(flux):
    value = np.asarray(flux)
    return np.sign(value)*(np.minimum(abs(value), KNEE)/L_LINEAR+
                           np.maximum(abs(value)-KNEE, 0)/L_SATURATED)


def _inverse(value, factor):
    """Exact inverse of lambda + factor*excitation(lambda), continuous at knee."""
    edge = KNEE*(1+factor/L_LINEAR)
    if abs(value) <= edge:
        return value/(1+factor/L_LINEAR)
    offset = KNEE*(1/L_LINEAR-1/L_SATURATED)
    return np.sign(value)*(abs(value)-factor*offset)/(1+factor/L_SATURATED)


def simulate(primary, fs, *, burden, initial_flux=0, substeps=16):
    """Integrate linearly interpolated ratio current; return sample-aligned state."""
    u = np.asarray(primary, dtype=float)
    if (u.ndim != 1 or u.size < 2 or not np.all(np.isfinite(u)) or
            not np.isfinite(fs) or fs <= 0 or not np.isfinite(burden) or burden <= 0 or
            not np.isfinite(initial_flux) or isinstance(substeps, bool) or
            not isinstance(substeps, (int, np.integer)) or not 1 <= substeps <= 256):
        raise ValueError('Finite one-dimensional current and positive finite circuit parameters required.')
    flux = np.empty_like(u)
    flux[0] = initial_flux
    factor = burden/(2*fs*substeps)
    for i in range(1, len(u)):
        value = flux[i-1]
        for step in range(substeps):
            before = u[i-1]+(u[i]-u[i-1])*step/substeps
            after = u[i-1]+(u[i]-u[i-1])*(step+1)/substeps
            value = _inverse(value+factor*(before+after-excitation(value)), factor)
        flux[i] = value
    magnetizing = excitation(flux)
    return dict(secondary=u-magnetizing, flux=flux, excitation=magnetizing)
