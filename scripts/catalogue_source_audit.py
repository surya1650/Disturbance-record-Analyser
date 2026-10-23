"""Private source quality and provisional-registry comparison; never modifies inputs."""
import argparse
import json
from pathlib import Path

from dranalyser.registry.catalogue import identity, reciprocal_candidates
from dranalyser.registry.catalogue_io import read_catalogue
from dranalyser.registry.loader import load_line


def audit(catalogue_path, registry, candidate=None):
    envelope = read_catalogue(catalogue_path)
    cat = envelope['catalogue']
    rows = cat['rows']
    result = {'catalogue_hash': envelope['catalogue_hash'], 'source': cat['source'], 'summary': cat['summary'],
              'value_review_rows': [{k: row[k] for k in ('id', 'sheet', 'row', 'url', 'station', 'feeder', 'raw', 'issues')}
                                    for row in rows if not row['electrical_values_parseable']],
              'registry': [], 'accepted_field_cases': 0,
              'limits': 'Source comparisons and candidate terminal reversals are advisory. No source row is '
                        'a patrol confirmation, approved topology or authenticated event-effective settings.'}
    for path in sorted(Path(registry).glob('*.yaml')):
        line = load_line(str(path))
        stations = {end: identity(t.substation) for end, t in line.terminals.items()}
        exact = [r for r in rows if r['kv'] == line.kv and
                 identity(r['station']) == stations.get('S') and identity(r['feeder'].rstrip(' -')) == stations.get('R')]
        result['registry'].append({'line_id': line.id, 'path': str(path.resolve()),
            'model_review_required': line.model_review_required,
            'source_candidates': [{k: row[k] for k in ('id', 'url', 'station', 'feeder', 'length_km', 'z1', 'z0')}
                                  for row in exact],
            'reciprocal_candidates': [reciprocal_candidates(cat, row['id']) for row in exact],
            'status': 'review required; no active registry value changed by audit'})
    if candidate:
        line = load_line(candidate)
        result['prepared_candidate'] = {'path': str(Path(candidate).resolve()), 'line_id': line.id,
            'length_km': line.length_km, 'z1_primary_ohm': [line.z1.real, line.z1.imag],
            'z0_primary_ohm': [line.z0.real, line.z0.imag], 'towers': len(line.towers),
            'model_review_required': line.model_review_required}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue', required=True)
    parser.add_argument('--registry', default='data/registry')
    parser.add_argument('--candidate')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    result = audit(args.catalogue, args.registry, args.candidate)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Versioned audit output; do not replace an earlier run.
    with target.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result['summary']))


if __name__ == '__main__':
    main()
