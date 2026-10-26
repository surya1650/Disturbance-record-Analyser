"""Research six-channel shape screen and separate independent truth metrics."""
import numpy as np

from dranalyser.dsp.detect import detect_clipping
from scripts.acquisition_ct_validation import projection
from scripts.acquisition_quality_candidate import assess
from tests.full_record_signals import RATIOS

NAMES = ('IA', 'IB', 'IC', 'VA', 'VB', 'VC')


def record_quality(rec, freq, bounds):
    """Frozen scalar math in secondary A or V; never authorization to locate.

    For voltage this transfers the dimensionless shape budgets and uses the
    analogous numerical 1e-9 V floor, not an engineering VT-quality criterion.
    Caller-supplied window indices do not prove fault/stage identity.
    """
    out = dict(status='withheld', authorizes_location=False, reason='', channels={},
               window_basis='caller-supplied sample indices; no stage identity inference')
    if (rec.blocked() or rec.nrates > 1 or rec.n < 2 or not np.isfinite(rec.fs) or rec.fs <= 0 or
            not np.isfinite(freq) or freq <= 0 or not np.all(np.isfinite(rec.t)) or
            not np.allclose(np.diff(rec.t), 1/rec.fs, rtol=.01, atol=1e-7)):
        return dict(out, reason='Blocked or unsupported acquisition.')
    if (not isinstance(bounds, (tuple, list)) or len(bounds) != 2 or
            any(isinstance(i, bool) or not isinstance(i, (int, np.integer)) for i in bounds) or
            not 0 <= bounds[0] < bounds[1] <= rec.n):
        return dict(out, reason='Unsupported sample-index window.')
    lo, hi = bounds
    if (hi-lo)*freq/rec.fs < 4:
        return dict(out, reason='Under four cycles of guarded research support.')
    for name in NAMES:
        value, raw, meta = rec.analog.get(name), rec.raw_analog.get(name), rec.analog_meta.get(name)
        if (value is None or raw is None or meta is None or len(value) != rec.n or len(raw) != rec.n or
                not np.all(np.isfinite(value)) or not np.all(np.isfinite(raw)) or
                not meta.normalised or not np.all(np.isfinite([meta.primary, meta.secondary, meta.adc_min, meta.adc_max])) or
                min(meta.primary, meta.secondary) <= 0 or meta.adc_min >= meta.adc_max):
            return dict(out, reason='Incomplete/nonfinite channels, ratios or ADC metadata.')
        scalar = assess(value[lo:hi]*(meta.secondary/meta.primary), rec.fs, freq)
        out['channels'][name] = {k: v for k, v in scalar.items() if k not in ('policy', 'authorizes_location')}
        out['channels'][name]['unit'] = 'secondary_A' if name[0] == 'I' else 'secondary_V'
    clipped = detect_clipping(rec.raw_analog, rec.analog_meta)
    out['clipped_channels'] = clipped
    if clipped:
        return dict(out, reason='ADC clipping; scalar shape cannot clear this screen.')
    if any(row['status'] != 'candidate_pass' for row in out['channels'].values()):
        return dict(out, reason='At least one current/voltage shape screen did not pass.')
    return dict(out, status='candidate_pass', reason='Six bounded shape screens passed; production gates remain authoritative.')


def truth_errors(pair, truth):
    """Complete-cycle quadrature on physical sample supports, never DSP inputs."""
    terminals = {}
    maxima = dict(maximum_current_error=0., maximum_voltage_error=0., maximum_ct_current_error=0.,
                  maximum_i2_error_over_floor=0.)
    a = np.exp(2j*np.pi/3)
    for end, rec in pair.items():
        source = truth[end]
        lo, hi = source['window_indices']
        fs, freq = source['fs_true'], source['freq_true']
        if int((hi-1-lo)*freq/fs) < 1:
            terminals[end] = dict(status='unsupported', reason='No complete cycle for independent truth quadrature.')
            continue
        ph = {}
        for kind in ('ideal', 'ct_only', 'measured'):
            waves = source[kind] if kind != 'measured' else {n: rec.analog[n]/RATIOS[n[0]] for n in NAMES}
            ph[kind] = {n: projection(waves[n][:hi], fs, freq, lo)/np.sqrt(2) for n in NAMES}
        errors = {}
        for name in NAMES:
            family = max(abs(ph['ideal'][n]) for n in NAMES if n[0] == name[0])
            denominator = max(abs(ph['ideal'][name]), .01*family, 1e-6)
            errors[name] = float(abs(ph['measured'][name]-ph['ideal'][name])/denominator)
            key = 'maximum_current_error' if name[0] == 'I' else 'maximum_voltage_error'
            maxima[key] = max(maxima[key], errors[name])
            if name[0] == 'I':
                maxima['maximum_ct_current_error'] = max(maxima['maximum_ct_current_error'],
                    float(abs(ph['ct_only'][name]-ph['ideal'][name])/denominator))
        reference = [ph['ideal'][n] for n in NAMES[:3]]
        measured = [ph['measured'][n] for n in NAMES[:3]]
        i1 = (reference[0]+a*reference[1]+a*a*reference[2])/3
        i2 = (reference[0]+a*a*reference[1]+a*reference[2])/3
        actual_i2 = (measured[0]+a*a*measured[1]+a*measured[2])/3
        floor = max(abs(i2), .01*abs(i1), 1e-6)
        error_i2 = float(abs(actual_i2-i2)/floor)
        maxima['maximum_i2_error_over_floor'] = max(maxima['maximum_i2_error_over_floor'], error_i2)
        terminals[end] = dict(status='evaluated', phase_errors=errors, i2_error_over_floor=error_i2,
            i2_denominator_secondary_a=float(floor), sample_rate_relative_error=float(abs(rec.fs/fs-1)),
            true_frequency_hz=freq, true_fs=fs, window_indices=[lo, hi],
            ct_channels=source['ct_channels'], ct_peak_flux_knee=source['ct_peak_flux_knee'],
            ct_balance_max_residual=source['ct_balance_max_residual'])
    complete = all(row['status'] == 'evaluated' for row in terminals.values())
    return dict(terminals=terminals, **(maxima if complete else {k: None for k in maxima}),
                harmful_measurement=bool(max(maxima['maximum_current_error'], maxima['maximum_voltage_error'],
                    maxima['maximum_i2_error_over_floor']) > .05) if complete else None)
