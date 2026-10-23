"""Read-only replay of source-bound field cases through the existing analyser."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..comtrade.conformance import check
from ..comtrade.parser import ComtradeError, read_cff, read_comtrade
from ..dsp.pipeline import analyse
from ..faultloc.ensemble import TerminalInput, locate
from ..registry.catalogue import digest
from ..registry.loader import load_line
from .acceptance import evaluate


def proof(root, evidence):
    if not isinstance(evidence, dict) or not evidence.get('path') or not evidence.get('sha256'):
        raise ValueError('Evidence requires a path and exact SHA-256.')
    path = (root/evidence['path']).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest() != evidence['sha256']:
        raise ValueError('Evidence checksum mismatch: '+str(path))
    return path


def replay(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if manifest.get('schema') != 'dranalyser.field-acceptance.v1':
        raise ValueError('Unsupported field acceptance manifest.')
    root, results = manifest_path.parent, []
    protocol = manifest['protocol']
    for item in manifest.get('cases', []):
        row = {'event_id': item.get('event_id', ''), 'reasons': [], 'record_hashes': [],
               'executed_at': datetime.now(timezone.utc).isoformat(), 'estimated_km': None,
               'evidence_verified': False}
        results.append(row)
        try:
            line = load_line(str(proof(root, item.get('line'))))
            row.update(line_id=line.id, line_km=line.length_km)
            review, truth = item.get('review', {}), item.get('truth', {})
            proof(root, review)
            proof(root, truth)
            if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
                raise ValueError('Acceptance review must name a reviewer.')
            confirmations = ('same_incident_and_stage', 'terminal_identity', 'phase_mapping',
                             'ct_vt_scaling_and_polarity', 'event_effective_line_and_topology',
                             'independent_patrol_truth')
            if any(review.get(k) is not True for k in confirmations):
                raise ValueError('All source-bound input/truth review declarations are required.')
            if truth.get('independent') is not True:
                raise ValueError('Relay output and analyser predictions are not independent patrol truth.')
            row.update(truth_km=truth.get('chainage_km'), truth_uncertainty_km=truth.get('uncertainty_km'))
            records = item.get('records', {})
            if not records or set(records)-{'S', 'R'}:
                raise ValueError('Explicit S/R recording assignments are required.')
            analyses = {}
            evidence_paths = []
            for end, declaration in records.items():
                path = (root/declaration['path']).resolve()
                rec = (read_cff(str(path), channel_mapping=declaration.get('channel_mapping')) if path.suffix.lower() == '.cff'
                       else read_comtrade(str(path), channel_mapping=declaration.get('channel_mapping')))
                if rec.content_hash != declaration.get('record_hash'):
                    raise ValueError('Recording hash differs from frozen declaration.')
                row['record_hashes'].append(rec.content_hash)
                check(rec, nominal_kv=line.kv)
                evidence_paths.append(str(path))
                if rec.blocked():
                    # Legitimate conformance refusal is retained in the acceptance denominator.
                    row['refusal_reason'] = '; '.join(str(f) for f in rec.flags)
                else:
                    terminal = line.terminals[end]
                    an = analyse(rec, vt_type=terminal.it.vt_type)
                    analyses[end] = TerminalInput(an, end, zs1=terminal.zs1, zs0=terminal.zs0,
                                                  clock_good=False, polarity=terminal.i_polarity)
            row['evidence_verified'] = True
            row['source_paths'] = evidence_paths
            if len(analyses) != len(records):
                continue
            result = locate(line, analyses)
            row.update(method=result.method, mode=result.mode, refusal_reason='; '.join(result.caveats))
            if result.ok:
                row.update(estimated_km=result.km_from_S, diagnostic_interval_km=list(result.interval_km))
        except (ValueError, KeyError, OSError, TypeError, ComtradeError) as exc:
            row['reasons'].append(type(exc).__name__+': '+str(exc))
    return {'schema': 'dranalyser.field-acceptance-result.v1', 'manifest_sha256': hashlib.sha256(raw).hexdigest(),
            'protocol_hash': digest(protocol), 'protocol': protocol, **evaluate(protocol, results)}


def template():
    return {'schema': 'dranalyser.field-acceptance.v1', 'protocol': {
        'name': '', 'frozen_at': '', 'planned_event_ids': [], 'training_line_ids': [],
        'min_events': None, 'max_p95_error_pct': None, 'min_located_fraction': None}, 'cases': []}
