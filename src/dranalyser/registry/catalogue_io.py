"""Local snapshot/catalogue files. Operational source data belongs under out/."""
import json
from pathlib import Path

import yaml

from .catalogue import SCHEMA, build_catalogue, digest
from .catalogue_review import reviewed_line


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save_new(path, content):
    """Idempotent same-content writes; never overwrite a different revision."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_text(encoding='utf-8') == content:
            return
        raise ValueError('Output exists with different content; use a new revision path: '+str(target))
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(content)


def import_snapshot(snapshot, output):
    catalogue = build_catalogue(read_json(snapshot))
    envelope = {'catalogue_hash': digest(catalogue), 'catalogue': catalogue}
    save_new(output, json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    return envelope


def read_catalogue(path):
    envelope = read_json(path)
    cat = envelope.get('catalogue', {})
    if cat.get('schema') != SCHEMA or envelope.get('catalogue_hash') != digest(cat):
        raise ValueError('Catalogue checksum/schema mismatch; reimport its immutable source snapshot.')
    return envelope


def export_registry(catalogue_path, review_path, output):
    cat = read_catalogue(catalogue_path)['catalogue']
    result = reviewed_line(cat, read_json(review_path))
    save_new(output, yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
    return result


def review_template(envelope):
    return {'catalogue_hash': envelope['catalogue_hash'], 'reviewer': '', 'reason': '',
        'line_id': '', 'circuit_id': '', 'terminals': {'S': '', 'R': ''}, 'parameter_row': '',
        'impedance_basis': '', 'parameter_evidence': '', 'parameter_conflict_resolution': '',
        'topology_evidence': '', 'double_circuit': None, 'series_compensated': None,
        'series_only_model_confirmed': None,
        'instrument_declarations': {e: {'vt_type': '', 'vt_location': '', 'i_polarity': None} for e in ('S', 'R')}}
