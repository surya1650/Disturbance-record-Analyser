"""Read-only acquisition evidence inventory; never a field-accuracy certificate.

Outputs stay in out/ by default because record identities and hashes are local
operational evidence. File/folder names are not accepted as terminal truth.
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import yaml

from dranalyser.comtrade.conformance import check
from dranalyser.comtrade.parser import read_cff, read_comtrade
from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc.model_domain import scalar_model_reasons
from dranalyser.registry.loader import load_line
from dranalyser.rules.evidence import relay_evidence


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(record_roots, registry, truth_databases=()):
    out = {'schema_version': 1, 'status': 'field acceptance not established',
           'records': [], 'registry': [], 'stored_truth': [],
           'missing_acceptance_evidence': [
               'Reviewed opposite-end identity and same physical fault stage, bound to exact record hashes.',
               'Approved event-effective line impedances/sections, topology and units with source evidence.',
               'Verified CT/VT scaling, polarity, mapping and acquisition limitations.',
               'Surveyed tower/chainage schedule with uncertainty; a generated span grid is insufficient.',
               'Independent patrol-confirmed location and uncertainty linked to this incident.',
               'Frozen acceptance protocol and held-out cases; one case cannot calibrate interval coverage.'],
           'limits': 'This read-only inventory cannot authenticate declarations, infer terminal identity, '
                     'verify circuit topology or establish fault-distance accuracy.'}
    paths = sorted({p.resolve() for root in record_roots for p in Path(root).rglob('*')
                    if p.is_file() and p.suffix.lower() in ('.cfg', '.cff')})
    for path in paths:
        row = {'path': str(path), 'file_sha256': sha256(path), 'status': 'unavailable'}
        out['records'].append(row)
        try:
            rec = read_cff(str(path)) if path.suffix.lower() == '.cff' else read_comtrade(str(path))
            check(rec)
            row.update(record_hash=rec.content_hash, station=rec.station, device_id=rec.device_id,
                       samples=rec.n, fs_hz=rec.fs, start_time=str(rec.start_time), trigger_time=str(rec.trigger_time),
                       flags=[str(f) for f in rec.flags], blocked=rec.blocked())
            if rec.blocked():
                row['status'] = 'blocked by conformance'
                continue
            an = analyse(rec)
            evidence = relay_evidence(an, str(path), end='')
            row.update(status='parsed and analysed; identity and field truth unverified',
                       flags=[str(f) for f in rec.flags], fault_type=an.fault_type,
                       clock_quality=evidence['clock_quality'], stages=evidence['stages'],
                       ct_saturation=an.saturation.detected, clipped_channels=an.clipping,
                       zero_sequence_voltage=an.zero_seq_voltage)
        except Exception as exc:
            row['error'] = type(exc).__name__+': '+str(exc)[:300]
    for path in sorted(Path(registry).glob('*.yaml')):
        row = {'path': str(path.resolve()), 'sha256': sha256(path), 'approval_status': 'unverified'}
        out['registry'].append(row)
        try:
            text = path.read_text(encoding='utf-8')
            raw, line = yaml.safe_load(text), load_line(str(path))
            row.update(line_id=line.id, provisional_marker='PROVISIONAL' in text.upper(),
                       generated_tower_grid=bool(raw.get('tower_span_km') and not raw.get('towers')),
                       scalar_model_reasons=scalar_model_reasons(line))
        except Exception as exc:
            row['error'] = type(exc).__name__+': '+str(exc)[:300]
    for path in truth_databases:
        path = Path(path).resolve()
        row = {'path': str(path), 'status': 'unreviewed; stored rows do not prove field truth'}
        out['stored_truth'].append(row)
        try:
            with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
                row['confirmation_rows'] = db.execute('SELECT COUNT(*) FROM ground_truth').fetchone()[0]
                row['incident_rows'] = db.execute('SELECT COUNT(*) FROM incident').fetchone()[0]
        except (sqlite3.Error, OSError) as exc:
            row['error'] = str(exc)[:300]
    out['summary'] = {'records': len(paths), 'analysed': sum(r['status'].startswith('parsed') for r in out['records']),
                      'registry_files': len(out['registry']), 'accepted_field_cases': 0}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', nargs='+', required=True)
    parser.add_argument('--registry', default='data/registry')
    parser.add_argument('--truth-db', nargs='*', default=[])
    parser.add_argument('--output', default='out/field-validation/evidence-inventory.json')
    args = parser.parse_args()
    result = inventory(args.records, args.registry, args.truth_db)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(result['summary']))
    print('Evidence saved:', target)
    print(result['status'])


if __name__ == '__main__':
    main()
