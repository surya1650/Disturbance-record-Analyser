"""Explicit incident-local line facts; originals and the shared registry stay intact."""
import copy
import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath

import yaml

from ..registry.loader import line_from_dict
from .line_reference_review import clean_reference_review, reference_provenance
from .source_lines import normalise_model

NUMBERS = ('length_km', 'kv', 'r1', 'x1', 'r0', 'x0')
CONFIRMATIONS = ('confirmed_line', 'uniform_line', 'confirmed_same_event')


def _label(record):
    path = PurePosixPath(record)
    stem = path.stem
    if re.fullmatch(r'(?:event|record|dr)[_ -]?\d*', stem, re.I) and path.parent.name:
        stem = path.parent.name
    return re.sub(r'[_\s]+', ' ', stem).strip()


def _text(value, field, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(field+' must be text of at most '+str(limit)+' characters.')
    return value.strip()


def clean_line_review(raw):
    allowed = {*NUMBERS, *CONFIRMATIONS, 'basis', 'sections', 'ends', 'reviewer', 'evidence',
               'reference_id', 'reference_reviewed'}
    if not isinstance(raw, dict) or set(raw)-allowed:
        raise ValueError('Line inputs accept declared length/impedances, named ends and review facts only.')
    out = {}
    for key in NUMBERS:
        value = raw.get(key)
        if value is not None and (type(value) not in (int, float) or value < 0 or value > 1e12
                or not math.isfinite(value) or (key not in ('r1', 'r0') and value == 0)):
            raise ValueError(key+' must be a finite valid physical value or unknown.')
        out[key] = value
    out['basis'] = raw.get('basis', '')
    if out['basis'] not in ('', 'per-km', 'total'):
        raise ValueError('State whether impedances are ohm/km or total ohm.')
    out['sections'] = normalise_model({'sections': raw.get('sections', [])})['sections']
    for section in out['sections']:
        for key, value in section.items():
            if value is not None and (value < 0 or value > 1e12
                    or (key in ('x1_ohm_per_km', 'x0_ohm_per_km') and value == 0)):
                raise ValueError('Section '+key+' must be a valid physical value or unknown.')
    for key in CONFIRMATIONS:
        if type(raw.get(key, False)) is not bool:
            raise ValueError(key+' must be an explicit boolean.')
        out[key] = raw.get(key, False)
    out['reviewer'] = _text(raw.get('reviewer', ''), 'Reviewer', 120)
    out['evidence'] = _text(raw.get('evidence', ''), 'Evidence', 2000)
    ends = raw.get('ends', {})
    if not isinstance(ends, dict) or set(ends)-{'S', 'R'}:
        raise ValueError('Choose physical S/R explicitly; recording order does not assign ends.')
    out['ends'] = {}
    for end in ('S', 'R'):
        if end not in ends:
            continue
        value = ends[end]
        if not isinstance(value, dict) or set(value)-{'record', 'name', 'current_direction', 'vt_type', 'vt_location'}:
            raise ValueError('An end accepts recording, display name, current direction and VT facts only.')
        record = value.get('record', '')
        _text(record, 'Recording', 220)
        if not record:
            continue
        if (not record.lower().endswith(('.cfg', '.cff')) or '\\' in record or ':' in record
                or PurePosixPath(record).is_absolute() or '..' in PurePosixPath(record).parts):
            raise ValueError('Choose an original incident CFG/CFF recording.')
        chosen = dict(record=record, name=_text(value.get('name', ''), 'End name', 120) or _label(record))
        for key, values in (('current_direction', ('unknown', 'bus-to-line', 'line-to-bus')),
                            ('vt_type', ('unknown', 'CVT', 'VT')), ('vt_location', ('unknown', 'line', 'bus'))):
            chosen[key] = value.get(key, 'unknown')
            if chosen[key] not in values:
                raise ValueError('Invalid '+key+' declaration.')
        out['ends'][end] = chosen
    records = [value['record'] for value in out['ends'].values()]
    if len(set(records)) != len(records):
        raise ValueError('One recording cannot represent both physical ends.')
    out.update(clean_reference_review(raw, out))
    return out


def clean_incident_line(value):
    if value is None or value == {}:
        return {}
    if (not isinstance(value, dict) or set(value)-{'version', 'line_id', 'review', 'source_sha256'}
            or value.get('version') != 1 or type(value.get('version')) is not int
            or not re.fullmatch(r'INCIDENT-[0-9a-f]{32}', str(value.get('line_id', '')))):
        raise ValueError('Invalid incident-local line review.')
    hashes = value.get('source_sha256')
    if not isinstance(hashes, dict) or not hashes or len(hashes) > 2000 or any(
            not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v)
            for k, v in hashes.items()):
        raise ValueError('Incident line review requires frozen source hashes.')
    return dict(version=1, line_id=value['line_id'], review=clean_line_review(value.get('review')),
                source_sha256=dict(hashes))


def validate_incident_line(row):
    entry = clean_incident_line((row.get('metadata') or {}).get('incident_line'))
    if not entry:
        return {}
    if (entry['line_id'] != 'INCIDENT-'+row['incident_id']
            or entry['source_sha256'] != {f['name']: f['sha256'] for f in row['files']}):
        raise ValueError('Line inputs belong to different incident/source bytes; review current files.')
    names = {f['name'] for f in row['files']}
    if any(end['record'] not in names for end in entry['review']['ends'].values()):
        raise ValueError('Line end selection is absent from this incident revision.')
    return entry


def incident_line_missing(entry):
    if not entry:
        return ['Supply incident line facts only when a physical distance is requested.']
    review, missing = entry['review'], []
    if review.get('reference_id') and not review.get('reference_reviewed'):
        missing.append('Review the published reference applicability to this actual conductor and circuit; it is not measured line data.')
    for key, label in (('length_km', 'line length in km'), ('kv', 'nominal line voltage in kV')):
        if review[key] is None:
            missing.append('Supply '+label+'.')
    if not review['sections']:
        for key in ('r1', 'x1'):
            if review[key] is None:
                missing.append('Supply positive-sequence '+key.upper()+'.')
        if not review['basis']:
            missing.append('State impedance units: ohm/km or total ohm.')
        if not review['uniform_line']:
            missing.append('Confirm a uniform line section or supply explicit section geometry/constants.')
    else:
        previous = 0
        for section in review['sections']:
            lo, hi = section.get('from_km'), section.get('to_km')
            if (lo is None or hi is None or hi <= lo or not math.isclose(lo, previous, rel_tol=0, abs_tol=1e-8)
                    or section.get('r1_ohm_per_km') is None or section['r1_ohm_per_km'] < 0
                    or section.get('x1_ohm_per_km') is None or section['x1_ohm_per_km'] <= 0):
                missing.append('Supply contiguous positive-length sections with valid R1/X1 in ohm/km.')
                break
            previous = hi
        if review['length_km'] is not None and not math.isclose(previous, review['length_km'], rel_tol=0, abs_tol=1e-8):
            missing.append('Section chainage must cover the supplied full line length.')
    if not review['ends']:
        missing.append('Choose at least one physical end explicitly.')
    for end, value in review['ends'].items():
        for key, label in (('current_direction', 'current direction'), ('vt_type', 'VT/CVT type'),
                           ('vt_location', 'voltage measurement location')):
            if value[key] == 'unknown':
                missing.append('Confirm '+end+' '+label+(' / recorded sign convention in Setup: which positive channel sign means bus into line; this is not power-flow direction.' if key == 'current_direction' else '.'))
    if len(review['ends']) == 2 and not review['confirmed_same_event']:
        missing.append('Confirm both recordings are the same event at opposite physical ends.')
    if not review['confirmed_line']:
        missing.append('Confirm this uncompensated single-circuit model applies; unsupported topology stays gated.')
    if not review['reviewer'] or not review['evidence']:
        missing.append('Record the reviewer and evidence for these line facts.')
    return list(dict.fromkeys(missing))


def prepare_incident_line(row, review):
    entry = clean_incident_line(dict(version=1, line_id='INCIDENT-'+row['incident_id'], review=review,
        source_sha256={f['name']: f['sha256'] for f in row['files']}))
    validate_incident_line(dict(row, metadata={'incident_line': entry}))
    inventory = {f['name'] for f in (row.get('bundle') or {}).get('files', []) if f.get('kind') == 'comtrade'}
    if any(end['record'] not in inventory for end in entry['review']['ends'].values()):
        raise ValueError('Select parsed recordings from this incident, not another attachment.')
    assignments = copy.deepcopy((row.get('metadata') or {}).get('assignments') or {})
    selected = {value['record']: end for end, value in entry['review']['ends'].items()}
    for name in inventory:
        value = assignments.setdefault(name, {})
        end = selected.get(name, '')
        if value.get('end') != end or (row.get('metadata') or {}).get('line_id') != entry['line_id']:
            value.pop('rx_review', None)
            value.pop('stage_review', None)
        value.update(end=end, role='primary' if end else 'excluded')
    return entry, assignments


def incident_line_model(metadata, bundle=None):
    entry = clean_incident_line(metadata.get('incident_line'))
    if not entry or metadata.get('line_id') != entry['line_id']:
        raise ValueError('The selected calculation does not use this incident-local line model.')
    missing = incident_line_missing(entry)
    if missing:
        raise ValueError(' '.join(missing))
    review, terms = entry['review'], {}
    assignments = metadata.get('assignments') or {}
    for end, chosen in review['ends'].items():
        assignment = assignments.get(chosen['record'], {})
        if assignment.get('end') != end or assignment.get('role') != 'primary':
            raise ValueError('Selected physical ends differ from the saved line inputs; edit and save the line facts first.')
    for name, assignment in assignments.items():
        end = assignment.get('end')
        if end and (end not in review['ends'] or (assignment.get('role') == 'primary'
                and review['ends'][end]['record'] != name)):
            raise ValueError('Selected physical ends differ from the saved line inputs; edit and save the line facts first.')
    records = ({f.name: f for f in bundle.records()} if bundle is not None else {})
    for end in ('S', 'R'):
        chosen = review['ends'].get(end)
        if chosen:
            record = records.get(chosen['record'])
            ratios = {key: getattr(record, key, 0) for key in ('ct_ratio', 'vt_ratio')}
            if record is None or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                                     for v in ratios.values()):
                raise ValueError(end+': source CT/VT scaling facts remain unavailable; save actual instrument ratings first.')
            terms[end] = dict(substation=chosen['name'], **ratios, vt_type=chosen['vt_type'],
                vt_location=chosen['vt_location'], i_polarity=1 if chosen['current_direction'] == 'bus-to-line' else -1)
        else:
            terms[end] = dict(substation='End '+end+' (not recorded)', ct_ratio=1, vt_ratio=1,
                vt_type='unknown', vt_location='unknown', i_polarity=1,
                instrument_basis='No recording at this end; unity is an unused normalization factor, not a physical rating.')
    if review['sections']:
        sections = [dict(from_km=s['from_km'], to_km=s['to_km'],
            **{k: s.get(k+'_ohm_per_km') for k in ('r1', 'x1', 'r0', 'x0')}) for s in review['sections']]
    else:
        factor = review['length_km'] if review['basis'] == 'total' else 1
        sections = [dict(from_km=0, to_km=review['length_km'],
            **{k: review[k]/factor if review[k] is not None else None for k in ('r1', 'x1', 'r0', 'x0')})]
    if any(value is not None and not math.isfinite(value) for section in sections
           for key, value in section.items() if key in ('r1', 'x1', 'r0', 'x0')):
        raise ValueError('Impedance conversion must produce finite ohm/km values; check length and units.')
    model = dict(id=entry['line_id'], name=' – '.join(value['name'] for value in review['ends'].values()),
        kv=review['kv'], sections=sections, terminals=terms, double_circuit=False, series_compensated=False,
        model_review_required=False, section_solver_enabled=False,
        review_provenance=dict(reviewer=review['reviewer'], evidence=review['evidence'],
            model_applicability='User confirmed an applicable uncompensated single-circuit model.',
            instruments='Ratios follow source declarations/reviews; not independent field verification.'))
    reference = reference_provenance(review)
    if reference:
        model['review_provenance']['line_reference'] = reference
    line_from_dict(model)
    return model


def freeze_incident_line(metadata, run, bundle=None):
    path = Path(run)/'line.yaml'
    path.write_text(yaml.safe_dump(incident_line_model(metadata, bundle), sort_keys=False), encoding='utf-8')
    return str(path)


def line_input_fingerprint(incident_id, revision, metadata):
    return hashlib.sha256(json.dumps(dict(incident_id=incident_id, revision=revision, metadata=metadata),
        sort_keys=True, allow_nan=False).encode()).hexdigest()
