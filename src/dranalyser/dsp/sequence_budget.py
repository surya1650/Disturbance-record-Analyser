"""Conditional additive-error bounds; never field confidence or authorization."""
import cmath
import math
from numbers import Complex, Real

SCOPE = 'Caller-supplied deterministic additive bounds only; excludes any error component not covered by them.'


def _unsupported(reason):
    return dict(status='unsupported', authorizes_location=False, reason=reason, bounds_scope=SCOPE)


def _real(value):
    try:
        return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))
    except (ValueError, OverflowError):
        return False


def dft_noise_radius(fs, freq, sample_bound, *, tau=None, half_cycle=False, uniform_grid=False):
    """Bound the matched linear RMS-DFT operator on a verified uniform local grid.

    Input/output bounds are in primary A. This does not bound frequency-model
    bias or all floating-point accumulation error, nor establish anti-aliasing.
    """
    if (uniform_grid is not True or not isinstance(half_cycle, bool) or
            not all(_real(v) for v in (fs, freq, sample_bound)) or
            fs <= 0 or freq <= 0 or sample_bound < 0 or
            tau is not None and (not _real(tau) or tau < 0)):
        return _unsupported('Finite sampling parameters, explicit uniform grid and nonnegative amplitude cap required.')
    fs, freq, sample_bound = float(fs), float(freq), float(sample_bound)
    ratio = fs/freq
    if not all(math.isfinite(v) for v in (ratio, 1/fs, 2*math.pi*freq)):
        return _unsupported('Unrepresentable samples per cycle, sample period or phase frequency.')
    n = round(ratio)
    n = max(n//2, 2) if half_cycle else n
    if n < 2:
        return _unsupported('At least two samples per kernel required.')
    try:
        factor = math.sqrt(2)
        if tau is not None:
            b = math.exp(-(1/fs)/max(float(tau), 1e-6))
            gain = abs(1-b*cmath.exp(-2j*math.pi*(freq/fs)))
            if gain == 0:
                return _unsupported('Unrepresentable mimic response.')
            factor *= (n-1)/n+(1+b)/(n*gain)
        factor += 64*math.ulp(factor)
        radius = sample_bound*factor
        if not all(math.isfinite(v) for v in (factor, radius)):
            return _unsupported('Nonfinite propagated kernel bound.')
    except (ArithmeticError, ValueError):
        return _unsupported('Unrepresentable kernel arithmetic.')
    return dict(status='conditional_bound', authorizes_location=False, bounds_scope=SCOPE,
                radius_primary_a=radius, coefficient_l1_upper_bound=factor, n_window=n,
                samples_per_cycle=ratio, uniform_grid_required=True,
                floating_point_interval_certified=False)


def i2_budget(currents, error_radii, *, provenance=''):
    """ABC primary RMS phasors and error circles -> conditional I2 error bound.

    No noise cap is inferred from a waveform. Provenance describes the supplied
    assumption; the function cannot establish that the assumption is true.
    """
    if not isinstance(provenance, str) or not provenance.strip():
        return _unsupported('Error-bound provenance is required; unknown errors are not zero.')
    try:
        if (len(currents) != 3 or len(error_radii) != 3 or
                any(not isinstance(z, Complex) or isinstance(z, bool) for z in currents) or
                any(not _real(r) or r < 0 for r in error_radii)):
            return _unsupported('Three finite ABC phasors and nonnegative radii required.')
        values = tuple(complex(z) for z in currents)
        radii = tuple(float(r) for r in error_radii)
        if not all(cmath.isfinite(z) for z in values):
            return _unsupported('Nonfinite current phasor.')
        a = cmath.exp(2j*math.pi/3)
        ia, ib, ic = (z/3 for z in values)
        i1, i2 = abs(ia+a*ib+a*a*ic), abs(ia+a*a*ib+a*ic)
        input_radius = sum(r/3 for r in radii)
        guard = 64*math.ulp(max(abs(z) for z in values))
        radius = input_radius+guard
        lo, hi = max(i2-radius, 0.), i2+radius
        floor = max(.01*(i1+radius), 1e-6)
        relative = radius/lo if lo > 0 else None
        finite = [i1, i2, input_radius, guard, radius, lo, hi, floor]
        if relative is not None:
            finite.append(relative)
        if not all(math.isfinite(v) for v in finite):
            return _unsupported('Nonfinite propagated sequence bound.')
    except (TypeError, ValueError, ArithmeticError):
        return _unsupported('Unsupported or unrepresentable current/error bounds.')
    reason = ('I2 is not separated from the supplied error radius.' if lo == 0 else
              'Guaranteed I2 is below the conservative signal floor.' if lo < floor else
              'Conditional relative error bound exceeds 5%.' if relative > .05 else
              'Supplied additive bounds imply the stated relative limit; assumptions remain unverified.')
    return dict(status='bounded_under_assumptions' if lo >= floor and relative <= .05 else 'withheld',
                authorizes_location=False, bounds_scope=SCOPE, provenance=provenance.strip(), reason=reason,
                measured_i1_primary_a=i1, measured_i2_primary_a=i2,
                input_i2_radius_primary_a=input_radius, numerical_guard_primary_a=guard,
                i2_radius_primary_a=radius, true_i2_magnitude_interval_primary_a=[lo, hi],
                required_signal_floor_primary_a=floor, relative_error_bound=relative,
                relative_error_limit=.05, floating_point_interval_certified=False)
