"""Saved, source-bound diagram declarations; never operational settings."""
import json
import math

from fastapi import HTTPException, Query

from .store import Conflict
from ..workbench.source_diagnostics import normalise_options
from ..workbench.source_inspection import _source


def clean_diagram(raw):
    if not isinstance(raw, dict) or set(raw)-{'reviewer', 'evidence', 'primary_scaling_confirmed', 'zone_basis', 'ct_ratio', 'vt_ratio', 'zones'}:
        raise ValueError('Supply reviewer, evidence, scaling declaration and explicit zone boundaries only.')
    out = {}
    for key in ('reviewer', 'evidence'):
        value = raw.get(key, '')
        if not isinstance(value, str) or len(value) > 2000:
            raise ValueError('Reviewer and evidence must be text of at most 2000 characters.')
        out[key] = value.strip()
    confirmed = raw.get('primary_scaling_confirmed', False)
    if type(confirmed) is not bool:
        raise ValueError('Confirm primary source scaling explicitly or leave it unconfirmed.')
    out['primary_scaling_confirmed'] = confirmed
    basis = raw.get('zone_basis', 'primary')
    if basis not in ('primary', 'secondary'):
        raise ValueError('Zone ohm basis must be primary or secondary.')
    out['zone_basis'] = basis
    for key in ('ct_ratio', 'vt_ratio'):
        value = raw.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 1e-9 <= value <= 1e12):
            raise ValueError('Settings CT/VT ratios must be finite positive values or blank.')
        out[key] = value
    zones = raw.get('zones', [])
    if not isinstance(zones, list) or len(zones) > 6:
        raise ValueError('Supply at most six declared phase-zone boundaries.')
    out['zones'] = []
    for zone in zones:
        if not isinstance(zone, dict) or set(zone) != {'name', 'shape', 'reach', 'angle', 'points'}:
            raise ValueError('Supply zone name, shape, reach, angle and explicit polygon vertices.')
        if not isinstance(zone['name'], str) or not 1 <= len(zone['name'].strip()) <= 80:
            raise ValueError('Each zone needs a name of at most 80 characters.')
        def number(v, low, high):
            return type(v) in (int, float) and math.isfinite(v) and low <= v <= high
        if zone['shape'] == 'mho':
            if not number(zone['reach'], 1e-9, 1e9) or not number(zone['angle'], -180, 180) or zone['points']:
                raise ValueError('A mho boundary requires positive reach, angle from -180 to 180 degrees and no polygon vertices.')
        elif zone['shape'] == 'polygon':
            points = zone['points']
            if zone['reach'] is not None or zone['angle'] is not None or not isinstance(points, list) or not 3 <= len(points) <= 32:
                raise ValueError('A polygon requires 3–32 explicit ordered R/X vertices and blank mho fields.')
            if any(not isinstance(p, list) or len(p) != 2 or not all(number(v, -1e9, 1e9) for v in p) for p in points):
                raise ValueError('Polygon vertices must be finite R/X pairs within the diagram range.')
        else:
            raise ValueError('Choose a mho or explicit polygon boundary.')
        out['zones'].append(dict(zone, name=zone['name'].strip()))
    if (confirmed or zones) and not (out['reviewer'] and out['evidence']):
        raise ValueError('Supply reviewer and supporting evidence before declaring scaling or zone boundaries.')
    return out


def install_diagram_inputs(app, store):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS diagram_inputs (incident_id TEXT NOT NULL,revision INTEGER NOT NULL,record TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(incident_id,revision,record))')

    def row_for(identity, revision, record):
        row = store.get(identity, revision)
        if row is None:
            raise HTTPException(404, 'Revision not found.')
        if not any(f['kind'] == 'comtrade' and f['name'] == record for f in (row.get('bundle') or {}).get('files', [])):
            raise ValueError('Select an original recording in this revision for diagram inputs.')
        return row

    @app.get('/api/incidents/{incident_id}/diagram-inputs')
    def get_inputs(incident_id: str, record: str, revision: int = Query(..., ge=1)):
        row_for(incident_id, revision, record)
        with store.connect() as db:
            saved = db.execute('SELECT version,payload FROM diagram_inputs WHERE incident_id=? AND revision=? AND record=?', (incident_id, revision, record)).fetchone()
        return dict(version=saved['version'] if saved else 0, **(json.loads(saved['payload']) if saved else dict(options=None, diagram=clean_diagram({}))))

    @app.put('/api/incidents/{incident_id}/diagram-inputs')
    def put_inputs(incident_id: str, body: dict):
        if set(body) != {'revision', 'record', 'version', 'options', 'diagram'}:
            raise ValueError('Supply revision, record, version, source choices and diagram declarations.')
        revision, version = body['revision'], body['version']
        if type(revision) is not int or revision < 1 or type(version) is not int or version < 0:
            raise ValueError('Use the displayed revision and input version.')
        if not isinstance(body['record'], str):
            raise ValueError('Select an original recording.')
        row = row_for(incident_id, revision, body['record'])
        source, _ = _source(store.root, row, body['record'])
        cleaned = dict(options=normalise_options(body['options'], source), diagram=clean_diagram(body['diagram']))
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT version FROM diagram_inputs WHERE incident_id=? AND revision=? AND record=?', (incident_id, revision, body['record'])).fetchone()
            if (prior['version'] if prior else 0) != version:
                raise Conflict('Diagram inputs changed in another tab. Reopen this recording before saving.')
            db.execute('INSERT INTO diagram_inputs VALUES(?,?,?,?,?) ON CONFLICT(incident_id,revision,record) DO UPDATE SET version=excluded.version,payload=excluded.payload', (incident_id, revision, body['record'], version+1, json.dumps(cleaned)))
        return dict(version=version+1, **cleaned)
