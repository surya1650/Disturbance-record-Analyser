"""Versioned location evidence for new revisions; the engine owns every estimate.

This adapter only serializes operational results. Diagnostic intervals are not
calibrated confidence coverage, and physical km always uses Line.m_to_km.
Old revisions remain immutable and can retain their legacy location_text.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from numbers import Integral, Real
from pathlib import Path


def public(value):
    """Strict JSON values, excluding private/callable diagnostic implementation details."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, complex):
        return {'real': public(value.real), 'imag': public(value.imag)}
    if isinstance(value, dict):
        return {str(k): public(v) for k, v in value.items()
                if not str(k).startswith('_') and not callable(v)}
    if isinstance(value, (list, tuple)):
        return [public(v) for v in value if not callable(v)]
    return None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode('utf-8')).hexdigest()


def summarize(location, line, line_path, analyses, used, *, reasons=()):
    """Capture exact eligible engine output without promoting rejected alternatives."""
    accepted = bool(location is not None and location.ok and location.method
                    and math.isfinite(location.km_from_S) and math.isfinite(location.km_from_R))
    windows = {}
    for end, analysis in analyses.items():
        windows[end] = dict(record=used[end], **asdict(analysis.window),
                            n_phasors=int(analysis.indices().size),
                            time_basis='Source-local seconds; not cross-end clock synchronization.')
    estimates = []
    for estimate in location.estimates if location else []:
        km = line.m_to_km(estimate.m) if line and estimate.ok and 0 <= estimate.m <= 1 else None
        eligible = bool(estimate.ok and km is not None and estimate.diagnostics.get('weight', 0) > 0)
        estimates.append(dict(method=estimate.method, ends=estimate.ends, accepted=eligible, valid=estimate.ok,
                              m=estimate.m, km_from_S=km, residual=estimate.residual,
                              reason=estimate.reason, diagnostics=estimate.diagnostics,
                              spread_pu=estimate.spread))
    caveats = list(location.caveats if location else reasons)
    if location is None and not caveats:
        caveats = ['No line definition supplied.' if line is None else 'No usable primary record reached analysis.']
    raw = Path(line_path).read_bytes() if line_path and line else None
    return public(dict(version=1, status='accepted' if accepted else 'refused' if location else 'not_computed',
        accepted=accepted, method=location.method if location else None,
        mode=location.mode if location else 'none', fault_type=location.fault_type if location else None,
        m=location.m if location else None, km_from_S=location.km_from_S if accepted else None,
        km_from_R=location.km_from_R if accepted else None, reference='S',
        terminals={end: terminal.substation for end, terminal in line.terminals.items()} if line else {},
        interval_km=location.interval_km if accepted else None,
        interval_kind='Diagnostic window spread; not calibrated confidence coverage.',
        estimates=estimates, diagnostics=location.diagnostics if location else {}, caveats=caveats,
        supported_windows=windows, source_records=dict(used),
        line=dict(id=line.id if line else None, sha256=hashlib.sha256(raw).hexdigest() if raw else None,
                  parameter_status='unverified' if line else 'not supplied')))


def bind_summary(summary, revision, parameter_status):
    """Bind the stored summary to the immutable job inputs, not a display selection."""
    result = public(summary)
    files = {f['name']: f['sha256'] for f in revision['files']}
    metadata = revision.get('metadata') or {}
    result['line']['parameter_status'] = parameter_status
    result['binding'] = dict(incident_id=revision['incident_id'], revision=revision['number'],
                             metadata_sha256=digest(metadata), files_sha256=files)
    result['source_sha256'] = files
    result['input_sha256'] = digest(dict(line_sha256=result['line']['sha256'], metadata=metadata, files=files))
    return result


def binding_reason(summary, revision, line_hash):
    """A stale/new-schema result never falls back to a number parsed from prose."""
    if not isinstance(summary, dict) or summary.get('version') != 1:
        return 'Unsupported structured location evidence version.'
    binding = summary.get('binding') or {}
    files = {f['name']: f['sha256'] for f in revision.get('files', [])}
    metadata = revision.get('metadata') or {}
    expected = dict(incident_id=revision['incident_id'], revision=revision['number'],
                    metadata_sha256=digest(metadata), files_sha256=files)
    if binding != expected or summary.get('source_sha256') != files:
        return 'Stored location source/revision/input binding differs from this revision.'
    if (summary.get('line') or {}).get('sha256') != line_hash:
        return 'Stored location line-model hash differs from the frozen definition.'
    if summary.get('input_sha256') != digest(dict(line_sha256=line_hash, metadata=metadata, files=files)):
        return 'Stored location input hash differs from this revision.'
    if summary.get('source_records') != (revision.get('result') or {}).get('used'):
        return 'Stored location end assignments differ from this revision.'
    return ''


def snapshot_location(summary, revision, line_hash, length_km, model_eligible, text):
    """Expose validated evidence to reports; never turn a refusal into an overlay."""
    reason = binding_reason(summary, revision, line_hash)
    if reason:
        return dict(status='Not available', text=reason, km_from_S=None, overlay_eligible=False,
                    provenance='Structured operational evidence binding failed.')
    status = summary.get('status')
    caveats = summary.get('caveats') or []
    km, remote, fraction = (summary.get(k) for k in ('km_from_S', 'km_from_R', 'm'))
    def finite(value):
        return type(value) in (int, float) and math.isfinite(value)
    numeric = (finite(km) and finite(remote) and finite(fraction) and length_km is not None
               and 0 <= fraction <= 1 and 0 <= km <= length_km and 0 <= remote <= length_km
               and math.isclose(km + remote, length_km, rel_tol=1e-9, abs_tol=1e-9))
    accepted = (summary.get('accepted') is True and status == 'accepted' and numeric
                and isinstance(summary.get('method'), str) and bool(summary['method'].strip())
                and summary.get('mode') in ('single-ended', 'two-ended'))
    explanation = text if accepted else '; '.join(str(c) for c in caveats) or 'No accepted operational location.'
    if summary.get('accepted') is True and not accepted:
        explanation = 'Structured location does not contain an eligible method-labelled physical distance.'
    eligible = accepted and model_eligible
    return dict(status='Existing conditional estimate' if accepted else 'Not available', text=explanation,
                km_from_S=km if accepted else None, km_from_R=remote if accepted else None,
                method=summary.get('method') if accepted else None, mode=summary.get('mode'),
                fault_type=summary.get('fault_type'), reference='S', overlay_eligible=eligible,
                summary=summary, provenance='Versioned operational result bound to frozen source, input and line hashes; declared engineering inputs remain conditional.')
