"""Display-only measurement-basis evidence; never changes samples or ratings.

The voltage/current bands below are deliberately broad UI screening policies,
not transformer-rating inference, calibration or nominal-system-voltage checks.
"""
from bisect import bisect_left
from decimal import Decimal, InvalidOperation
import math

from ..comtrade.parser import detect_phase_naming, map_channel
from ..dsp.cursor_fourier import PreparedTimeline, cursor_fourier
from .source_display import timeline

_ROLES = ('VA', 'VB', 'VC', 'IA', 'IB', 'IC')
_TINY = 2.2250738585072014e-308
_NOTE = ('Display evidence only; confirm the actual recording basis and a/b gains. '
         'No CT/VT ratio is inferred or applied, and no basis changes automatically.')


def _number(value):
    try:
        if isinstance(value, bool) or value is None:
            return None
        result = float(value)
        if not math.isfinite(result) or (result == 0 and Decimal(str(value)) != 0):
            return None
        return result
    except (ValueError, TypeError, OverflowError, InvalidOperation):
        return None


def _ps(row):
    return str(row.get('primary_secondary', row.get('ps', ''))).strip().upper()


def _before_trigger(source, axis, end_s):
    origin = axis.get('declared_origin') or {}
    first = _number(origin.get('first_offset_s'))
    trigger = timeline(source)['trigger_offset_s']
    return (str(axis.get('basis', '')).startswith('DAT source timestamps as declared;')
            and origin.get('status') == 'available'
            and origin.get('basis') == 'Original DAT timestamps × declared time multiplier'
            and first is not None and first >= 0 and trigger is not None
            and first+end_s < trigger-1e-12)


def _ratio(row):
    primary, secondary = (_number(row.get(k)) for k in ('primary', 'secondary'))
    if primary is None or secondary is None or min(primary, secondary) <= 0:
        return None
    factor = primary/secondary
    return factor if math.isfinite(factor) and factor >= _TINY else None


def _export_values(values, a, b, factor):
    """Missing S ratios leave raw observations: apply only declared a/b and unit.

    This does not establish that the resulting engineering values are primary
    or secondary. Conversion defects stay unavailable, as in source decoding.
    """
    result = []
    for raw in values:
        value = _number(raw) if not isinstance(raw, str) else None
        if value is None:
            result.append(None)
            continue
        product = value*a
        converted = (product+b)*factor
        if (not math.isfinite(converted) or
                (value != 0 and (product == 0 or abs(product) < _TINY)) or
                (converted != 0 and abs(converted) < _TINY)):
            return None
        result.append(converted)
    return result


def _channel(channel, original, effective, naming, review):
    identity = channel.get('key', channel.get('id', ''))
    unit = str(original.get('declared_units', original.get('unit', ''))).strip().upper()
    physical_unit = 'V' if unit in ('V', 'KV') else 'A' if unit in ('A', 'KA') else None
    role = channel.get('meaning')
    if role not in _ROLES:
        role = map_channel(channel.get('label', original.get('label', '')), unit, original.get('phase', ''), naming)
    row = dict(id=identity, label=channel.get('label', original.get('label', identity)),
               meaning=role if role in _ROLES else None, original_ps=_ps(original),
               effective_ps=_ps(effective), declared_unit=unit, unit=physical_unit,
               rms=None, fundamental_rms=None, status='unavailable', support=None,
               reason='Physical units, finite nonzero a, finite b and explicit P/S declarations are required.')
    a, b = _number(original.get('a')), _number(original.get('b'))
    if (physical_unit is None or a is None or not abs(a) >= _TINY or b is None or
            row['original_ps'] not in ('P', 'S') or row['effective_ps'] not in ('P', 'S')):
        return row, None
    if role not in _ROLES or physical_unit != ('V' if role.startswith('V') else 'A'):
        row['reason'] = 'An unambiguous corresponding phase voltage/current identity is required.'
        return row, None
    if _number(channel.get('skew_us')) != 0:
        row['reason'] = 'Declared zero sample skew is required for corresponding one-cycle phase evidence.'
        return row, None
    values = channel.get('values', [])
    prefix = str(channel.get('units', '')).split(' ', 1)[0].upper()
    ratio = _ratio(effective)
    if prefix != physical_unit:
        if (channel.get('units') == 'raw counts' and row['effective_ps'] == 'S' and
                ratio is None and not review):
            values = _export_values(values, a, b, 1000 if unit in ('KV', 'KA') else 1)
            if values is None:
                row['reason'] = 'Declared a/b or physical-unit conversion exceeds numeric range; counts stay unknown.'
                return row, None
            row['measurement_basis'] = 'Recorded a/b and physical units only; missing S ratio remains unresolved.'
        else:
            row['reason'] = 'Decoded observations remain counts or incompatible units; no physical magnitude is assumed.'
            return row, None
    else:
        row['measurement_basis'] = 'Already decoded source values; gains, units and valid declared S ratios are not applied again.'
    row['basis_status'] = ('reviewed_primary' if identity in review.get('primary_channels', []) else
                           'reviewed_secondary' if identity in review.get('ratios', {}) else
                           'cfg_primary' if row['effective_ps'] == 'P' else
                           'cfg_secondary' if ratio is not None and ratio != 1 else 'unresolved')
    row['reason'] = ''
    row['status'] = 'awaiting_support'
    return row, values


def measurement_basis_hint(source):
    """Return source-bound, one-cycle RMS evidence without modifying ``source``.

    The first complete nominal cycle is inspected. It is only called
    pre-trigger when recorded timestamps support that description; neither a
    healthy pre-fault baseline nor actual transformer ratings are established.
    """
    out = dict(status='ambiguous', reason='A complete supported phase measurement is required.',
               message='', channels=[], support=None, display_only=True,
               applies_automatically=False, scaling_verified=False, authorizes_location=False,
               source_sha256=dict(source.get('source_sha256') or {}),
               content_hash=source.get('content_hash', ''),
               policy=dict(primary_voltage_min_v=10000, secondary_voltage_reference_v=[110/math.sqrt(3), 110],
                           secondary_voltage_tolerance=.20, secondary_current_reference_a=1,
                           secondary_current_tolerance=.50), note=_NOTE)
    original = source.get('recorded_header_inventory', source.get('header_inventory', []))
    effective = {c.get('id'): c for c in source.get('header_inventory', [])}
    headers = {c.get('id'): c for c in original}
    naming = detect_phase_naming([c.get('label', '') for c in original if c.get('kind') == 'analog'])
    review = source.get('instrument_review') or source.get('applied_review') or {}
    values = {}
    for channel in source.get('channels', []):
        identity = channel.get('key', channel.get('id'))
        row, observations = _channel(channel, headers.get(identity, {}), effective.get(identity, {}), naming, review)
        out['channels'].append(row)
        if observations is not None:
            values[identity] = observations
    axis = source.get('axis') or {}
    prepared = PreparedTimeline(axis.get('elapsed_s', []))
    frequency = _number(source.get('nominal_frequency_hz'))
    reason = prepared.reason
    if axis.get('status') != 'source_time_inspection' or frequency is None or not 40 <= frequency <= 70:
        reason = 'Supported actual source times and a declared 40–70 Hz frequency are required; no magnitude basis is guessed.'
    elif not reason:
        times = prepared.coordinates
        index = bisect_left(times, times[0]+1/frequency-1e-12)
        if index >= len(times):
            reason = 'The capture does not contain a complete nominal-cycle support.'
        else:
            measured = cursor_fourier(prepared, values, frequency, index,
                                      break_indices=source.get('break_indices', []))
            reason = measured.get('reason', '')
            window = measured.get('window')
            if window and not reason:
                before_trigger = _before_trigger(source, axis, window['end_s'])
                support = dict(start_s=window['nominal_start_s'], end_s=window['end_s'],
                    first_sample_index=window['start_index'], last_sample_index=index,
                    sample_count=index+1-window['start_index'], window_s=1/frequency,
                    observed_start_s=window['start_s'], interval=window['interval'],
                    observation='before recorded trigger' if before_trigger else 'first complete source cycle',
                    prefault_established=False,
                    basis='Equal-weight RMS of actual native samples over one complete nominal cycle; includes DC and harmonics.')
                out['support'] = support
                for row in out['channels']:
                    fit = measured['channels'].get(row['id'], {})
                    if fit.get('status') == 'observed':
                        row.update(status='measured', rms=fit['total_rms'], fundamental_rms=fit['fundamental_rms'],
                                   dc=fit['dc'], relative_residual=fit['relative_residual'], support=dict(support))
                    elif row['status'] == 'awaiting_support':
                        row.update(status='unavailable', reason=fit.get('reason', 'No supported complete cycle.'))
    if reason:
        out['reason'] = reason
        for row in out['channels']:
            if row['status'] == 'awaiting_support':
                row.update(status='unavailable', reason=reason)
    else:
        _classify(out)
    out['message'] = out['reason']
    return out


def _classify(out):
    rows = out['channels']
    groups = {role: [c for c in rows if c['meaning'] == role] for role in _ROLES}
    voltage = [groups[role][0] for role in _ROLES[:3] if len(groups[role]) == 1]
    phases = [groups[role][0] for role in _ROLES if len(groups[role]) == 1]
    if len(voltage) != 3 or any(c['status'] != 'measured' for c in voltage):
        out['reason'] = 'Three unambiguous supported phase voltages are required; missing identities, counts and invalid gains remain ambiguous.'
        return
    statuses = {c.get('basis_status') for c in phases}
    if statuses <= {'cfg_primary', 'reviewed_primary'}:
        out.update(status='reviewed_primary' if 'reviewed_primary' in statuses else 'cfg_primary',
                   reason='Effective P values are preserved after recorded gains and unit conversion; no CT/VT multiplication is applied. Physical scaling remains unverified.')
    elif statuses <= {'cfg_secondary', 'reviewed_secondary'}:
        out.update(status='reviewed_secondary' if 'reviewed_secondary' in statuses else 'cfg_secondary',
                   reason='Valid declared S ratings have already converted these decoded values once. Their magnitude does not override the CFG basis; no second multiplication is applied.')
    elif statuses != {'unresolved'}:
        out['reason'] = 'The channels have different declared or reviewed bases; inspect each channel and confirm actual source evidence.'
    elif all(c['rms'] > 10000 and c['fundamental_rms'] >= .8*c['rms'] and c['relative_residual'] <= .25 for c in voltage):
        out.update(status='primary_sized_hint',
                   reason='The supported phase voltages are primary-sized, inconsistent with treating an unresolved S export with missing or unity ratings as ordinary secondary voltage. This is a magnitude hint only; explicitly confirm the actual basis before saving.')
    elif (len(phases) == 6 and all(c['status'] == 'measured' and c['fundamental_rms'] >= .8*c['rms'] and c['relative_residual'] <= .25 for c in phases)
          and any(all(.8*reference <= c['rms'] <= 1.2*reference for c in voltage) for reference in (110/math.sqrt(3), 110))
          and all(.5 <= c['rms'] <= 1.5 for c in phases[3:])):
        out.update(status='secondary_sized_hint',
                   reason='Joint supported voltages near 110 V or 110/√3 V and currents around 1 A look secondary-sized. This is a hint only: low load or voltage sag can overlap these magnitudes. Supply actual CT/VT ratings and explicitly confirm the basis; no ratio is inferred.')
    else:
        out['reason'] = 'The supported magnitudes do not distinguish primary from secondary. Low load, voltage sag/collapse and incomplete evidence remain ambiguous; confirm the actual basis and gains.'
