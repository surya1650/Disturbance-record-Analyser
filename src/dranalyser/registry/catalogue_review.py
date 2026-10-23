"""Explicit source-bound promotion to a separate provisional registry definition."""
from __future__ import annotations

import math
import re
import copy

from .catalogue import digest
from .loader import line_from_dict


def reviewed_line(catalogue, review):
    """No writes here. Reviewer declarations are provenance, not authentication."""
    if review.get('catalogue_hash') != digest(catalogue):
        raise ValueError('Review is stale or belongs to another catalogue.')
    for key in ('reviewer', 'reason', 'line_id', 'circuit_id', 'topology_evidence', 'parameter_evidence'):
        if not isinstance(review.get(key), str) or not review[key].strip():
            raise ValueError('Explicit '+key+' is required.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', review['line_id']):
        raise ValueError('Use a safe line ID with letters, digits, dots, underscores or hyphens.')
    if review.get('impedance_basis') not in ('primary_total_ohm', 'secondary_total_ohm'):
        raise ValueError('Confirm the source impedance base: primary_total_ohm or secondary_total_ohm.')
    rows = {r['id']: r for r in catalogue['rows']}
    selected = review.get('terminals', {})
    if set(selected) != {'S', 'R'} or selected['S'] == selected['R']:
        raise ValueError('Explicit distinct S/R source rows are required.')
    try:
        ends = {e: rows[selected[e]] for e in ('S', 'R')}
        params = rows[review['parameter_row']]
    except KeyError as exc:
        raise ValueError('All reviewed source rows must exist in this catalogue.') from exc
    if params['id'] not in selected.values():
        raise ValueError('Parameter row must be one of the selected terminal rows.')
    if not all(r['electrical_values_parseable'] for r in ends.values()):
        raise ValueError('Resolve source row errors before exporting; no input repair is performed.')
    if ends['S']['kv'] != ends['R']['kv'] or ends['S']['station'] == ends['R']['station']:
        raise ValueError('Selected rows require equal voltage and distinct terminal stations.')
    for key in ('double_circuit', 'series_compensated', 'series_only_model_confirmed'):
        if type(review.get(key)) is not bool:
            raise ValueError('Explicit boolean declaration required: '+key)
    if not review['series_only_model_confirmed']:
        raise ValueError('This export supports only a declared series-only scalar model.')
    length = params['length_km']
    scale = 1 if review['impedance_basis'] == 'primary_total_ohm' else params['vt_ratio']['ratio']/params['ct_ratio']['ratio']
    sections = [{'seq': 1, 'from_km': 0., 'to_km': length,
                 **{component+seq: params['z'+seq][component]*scale/length
                    for seq in ('1', '0') for component in ('r', 'x')}}]
    terms = {}
    for end, row in ends.items():
        declaration = review.get('instrument_declarations', {}).get(end, {})
        if (declaration.get('vt_type') not in ('VT', 'CVT') or
                declaration.get('vt_location') not in ('line', 'bus') or type(declaration.get('i_polarity')) is not int
                or declaration.get('i_polarity') not in (-1, 1)):
            raise ValueError('Each terminal requires explicit VT type/location and current polarity.')
        terms[end] = {'substation': row['station'], 'ct_ratio': row['ct_ratio']['ratio'],
                      'vt_ratio': row['vt_ratio']['ratio'], **{k: declaration[k] for k in ('vt_type', 'vt_location', 'i_polarity')}}
    conflicts = [key for key in ('length_km', 'z1', 'z0') if ends['S'][key] != ends['R'][key]]
    if conflicts and not review.get('parameter_conflict_resolution', '').strip():
        raise ValueError('Explain opposite-end parameter disagreements: '+', '.join(conflicts))
    result = {'id': review['line_id'], 'name': f"{ends['S']['station']} – {ends['R']['station']} / {review['circuit_id']}",
        'kv': params['kv'], 'parameter_status': 'PROVISIONAL: source-reviewed, field verification outstanding',
        'double_circuit': review['double_circuit'], 'series_compensated': review['series_compensated'],
        'sections': sections, 'terminals': terms, 'towers': [],
        'source_provenance': {'catalogue_hash': digest(catalogue), 'snapshot_hash': catalogue['snapshot_hash'],
                              'source': catalogue['source'], 'selected_rows': {e: {'id': r['id'], 'hash': r['row_hash'], 'url': r['url']}
                                                                             for e, r in ends.items()},
                              'review': review, 'unverified': ['field parameters and topology', 'CT/VT wiring',
                                  'event-effective settings', 'surveyed towers', 'patrol fault location']}}
    line = line_from_dict(result)
    if not math.isfinite(abs(line.z1)) or not line.z1.imag > 0:
        raise ValueError('Reviewed export has invalid positive-sequence impedance.')
    return result


def source_candidate(catalogue, selection, prior=None):
    """Use identified source data now, while withholding unreviewed model claims.

    Unlike reviewed_line, this path requires no declaration that topology or
    wiring has been verified. The main and stage solvers always refuse it.
    """
    if selection.get('catalogue_hash') != digest(catalogue):
        raise ValueError('Candidate selection is stale or from a different catalogue.')
    for key in ('line_id', 'identity_confirmation', 'basis_interpretation'):
        if not isinstance(selection.get(key), str) or not selection[key].strip():
            raise ValueError('Source candidate requires explicit '+key)
    if selection.get('impedance_basis') != 'primary_total_ohm':
        raise ValueError('Candidate import requires an explicit primary_total_ohm interpretation.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', selection['line_id']):
        raise ValueError('Invalid line ID.')
    rows = {r['id']: r for r in catalogue['rows']}
    ends = selection.get('terminals', {})
    if set(ends) != {'S', 'R'} or ends['S'] == ends['R']:
        raise ValueError('Candidate requires distinct explicitly identified S/R source rows.')
    try:
        selected = {e: rows[row_id] for e, row_id in ends.items()}
    except KeyError as exc:
        raise ValueError('Selected row is absent from this catalogue.') from exc
    s, r = selected['S'], selected['R']
    if not all(row['electrical_values_parseable'] for row in (s, r)):
        raise ValueError('Selected candidate has source value errors.')
    if any(s[k] != r[k] for k in ('kv', 'length_km', 'z1', 'z0')):
        raise ValueError('Candidate ends disagree on voltage, length or sequence impedance; explicit parameter review required.')
    if s['station'] == r['station']:
        raise ValueError('Candidate ends must identify different stations.')
    out = copy.deepcopy(prior or {})
    length = s['length_km']
    out.update(id=selection['line_id'], name=s['station']+' – '+r['station'], kv=s['kv'],
        model_review_required=True, parameter_status='PROVISIONAL: source supplied; electrical model review required',
        sections=[{'seq': 1, 'from_km': 0., 'to_km': length,
                   **{component+seq: s['z'+seq][component]/length for seq in ('1', '0') for component in ('r', 'x')}}],
        towers=[], source_provenance={'source': catalogue['source'], 'snapshot_hash': catalogue['snapshot_hash'],
            'selection': selection, 'rows': {e: {'id': row['id'], 'hash': row['row_hash'], 'url': row['url']}
                                           for e, row in selected.items()}, 'field_verified': False})
    out.pop('tower_span_km', None)
    terms = out.setdefault('terminals', {})
    for end, row in selected.items():
        terms.setdefault(end, {}).update(substation=row['station'], ct_ratio=row['ct_ratio']['ratio'],
                                        vt_ratio=row['vt_ratio']['ratio'])
    line_from_dict(out)
    return out
