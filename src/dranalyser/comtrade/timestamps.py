"""Bounded local DAT time recovery; never UTC or cross-record alignment evidence."""
import numpy as np

MAXIMUM_PERIOD_DEVIATION = .1


def recover_time(cfg, stamps, n):
    """Return grid, rate, informational warnings and explicit acquisition provenance.

    Invalid timestamps use a finite display-only placeholder with invalid status.
    The parser MUST attach a blocking acquisition flag for that status.
    """
    info = dict(status='declared', method='CFG sample rate', maximum_residual_s=None,
                maximum_interval_deviation_s=None, tolerance_period_fraction=MAXIMUM_PERIOD_DEVIATION,
                timemult=float(cfg.timemult) if np.isfinite(cfg.timemult) else None, alignment_eligible=False)
    if cfg.nrates >= 1 and cfg.rates and cfg.rates[0][0] > 0 and np.isfinite(cfg.rates[0][0]):
        if cfg.nrates == 1:
            fs = cfg.rates[0][0]
            return np.arange(n)/fs, fs, [], info
        t, previous, next_time = np.zeros(n), 0, 0.
        for rate, end in cfg.rates:
            end = min(int(end), n)
            if end <= previous or rate <= 0:
                continue
            t[previous:end] = next_time+np.arange(end-previous)/rate
            next_time, previous = t[end-1]+1/rate, end
        info['method'] = 'CFG multiple sample rates'
        return t, max(r for r, _ in cfg.rates if r > 0), ['multi-rate record; guarded location requires a supported sampling grid'], info

    def invalid(reason, display_period=None):
        # A finite placeholder supports inspection; its provenance and parser
        # block explicitly prohibit interpreting it as recovered acquisition.
        fs = 1000.
        if display_period is not None:
            fs = 1/display_period
        info.update(status='invalid', method='display-only placeholder', reason=reason,
                    display_rate_basis='untrusted DAT fit; inspection only' if display_period is not None else 'fixed 1000 Hz inspection placeholder')
        return np.arange(n)/fs, fs, [reason], info

    if cfg.nrates != 0:
        return invalid('Declared sample rate is invalid; DAT fitting cannot silently replace it.')
    raw = np.asarray(stamps, dtype=float)
    if n < 3 or raw.size != n or not np.all(np.isfinite(raw)):
        return invalid('DAT timestamps need at least three finite observations.')
    if not np.isfinite(cfg.timemult) or cfg.timemult <= 0:
        return invalid('DAT timestamp multiplier must be finite and positive.')
    # Subtract origin BEFORE scaling/fitting to avoid cancellation at large offsets.
    elapsed = (raw-raw[0])*(cfg.timemult*1e-6)
    if not np.all(np.isfinite(elapsed)) or np.any(np.diff(elapsed) <= 0):
        return invalid('DAT timestamps are not finite and strictly increasing.')
    k = np.arange(n, dtype=float)
    centered = k-np.mean(k)
    slope = float(centered@(elapsed-np.mean(elapsed))/(centered@centered))
    if not np.isfinite(slope) or slope <= 0 or not np.isfinite(1/slope):
        return invalid('DAT timestamp fit has no finite positive sampling rate.')
    residual = float(np.max(abs(elapsed-(np.mean(elapsed)+centered*slope))))
    interval = float(np.max(abs(np.diff(elapsed)-slope)))
    info.update(maximum_residual_s=residual, maximum_interval_deviation_s=interval)
    if max(residual, interval) > MAXIMUM_PERIOD_DEVIATION*slope:
        return invalid('DAT gap/jitter/drift exceeds the bounded 10% sample-period recovery policy.', slope)
    fs = 1/slope
    info.update(status='recovered', method='DAT centered linear fit', fitted_period_s=slope)
    return k*slope, fs, [f'rate derived from the DAT timestamp column: {fs:.1f} Hz; bounded recovery policy applied'], info


def sample_numbers_valid(numbers):
    values = np.asarray(numbers, dtype=float)
    return bool(values.size and np.all(np.isfinite(values)) and np.all(values >= 0)
                and np.all(values == np.floor(values)) and np.all(np.diff(values) == 1))
