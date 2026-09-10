"""Read a bounded native-sample interval from a revision's unchanged recording."""
from pathlib import Path

import numpy as np

from ..comtrade.parser import read_cff, read_comtrade

MAX_SAMPLES = 20000


def sample_interval(root, revision, filename, channel, lo, hi):
    if not np.isfinite(lo) or not np.isfinite(hi) or lo > hi:
        raise ValueError('Use finite increasing local interval bounds.')
    bundle = revision.get('bundle') or {}
    evidence = next((r for r in (revision.get('result') or {}).get('relay_evidence', [])
                     if r['file'] == filename and r['status'] == 'analysed'), None)
    item = next((f for f in bundle.get('files', []) if f['name'] == filename and f['kind'] == 'comtrade'), None)
    if not item or not evidence:
        raise ValueError('This revision has no analysed evidence for the requested record.')
    selected = next((c for c in item.get('channel_inventory', [])
                     if c['kind'] == 'analog' and c['selected'] == channel), None)
    if not selected:
        raise ValueError('Channel identity is unavailable in this revision; review and rerun if it predates channel inventories.')
    allowed = (Path(root)/'runs'/revision['incident_id']/str(revision['number'])).resolve()
    folder = Path(bundle['root']).resolve()
    path = (folder/filename).resolve()
    if not folder.is_relative_to(allowed) or not path.is_relative_to(folder) or not path.is_file():
        raise ValueError('Revision recording path is unavailable.')
    mapping = item.get('channel_mapping') or {}
    if filename.lower().endswith('.cff'):
        rec = read_cff(str(path), channel_mapping=mapping)
    else:
        dat = (folder/item['data_file']).resolve()
        if not dat.is_relative_to(folder) or not dat.is_file():
            raise ValueError('Revision DAT path is unavailable.')
        rec = read_comtrade(str(path), str(dat), channel_mapping=mapping)
    if rec.content_hash != evidence['record_hash'] or rec.content_hash != item['content_hash']:
        raise ValueError('Stored recording checksum differs from the analysed revision.')
    current = next((c for c in rec.notes['channel_inventory']
                    if c['kind'] == 'analog' and c['selected'] == channel), None)
    if not current or current['id'] != selected['id'] or current['label'] != selected['label']:
        raise ValueError('Replayed channel identity differs from the frozen revision.')
    if rec.n < 2 or not np.all(np.isfinite(rec.t)) or np.any(np.diff(rec.t) <= 0):
        raise ValueError('Native inspection requires finite increasing sample times.')
    if lo < rec.t[0]-1e-9 or hi > rec.t[-1]+1e-9:
        raise ValueError('Interval is outside this recording.')
    # Inclusive display bounds, distinct from the pipeline's half-open fault window.
    ids = np.flatnonzero((rec.t >= lo-1e-12) & (rec.t <= hi+1e-12))
    if len(ids) > MAX_SAMPLES:
        raise ValueError('Interval exceeds 20000 native samples; narrow the selected view.')
    values = rec.analog[channel][ids]
    finite = np.isfinite(values)
    metrics = {'status': 'measured' if len(ids) and np.all(finite) else 'no samples' if not len(ids) else 'non-finite samples',
               'rms': None, 'peak_abs': None, 'peak_local_s': None, 'sample_count': len(ids),
               'basis': 'Native sample-weighted RMS and measured absolute peak over inclusive display bounds; not the fault-analysis window.'}
    if metrics['status'] == 'measured':
        peak_index = int(np.argmax(np.abs(values)))
        amplitude = float(abs(values[peak_index]))
        metrics.update(rms=amplitude*float(np.sqrt(np.mean((values/amplitude)**2))) if amplitude else 0.0,
                       peak_abs=amplitude, peak_local_s=float(rec.t[ids[peak_index]]))
    meta = rec.analog_meta[channel]
    return {'file': filename, 'channel': channel, 'source': selected['label'], 'source_id': selected['id'],
            'record_hash': rec.content_hash, 'revision': revision['number'], 'range_s': [lo, hi],
            'unit': ('A' if channel.startswith('I') else 'V') if meta.normalised else 'unknown',
            'samples': [[int(i), float(rec.t[i]), float(v) if good else None] for i, v, good in zip(ids, values, finite, strict=True)],
            'metrics': metrics, 'note': 'Original zero-based sample indices and parser-normalized values; no resampling, inversion or interpolation. '
            'Sources and reviewed channel identities are verified against this revision. Read-only inspection does not update stored analysis.'}
