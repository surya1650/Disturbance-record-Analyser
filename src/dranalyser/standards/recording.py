"""Point-level WG-3 recording evidence; never proof of device configuration.

Profiles are explicit operator declarations. Full base tables are retained even
where this analyser has no semantic mapper; optional/bay-specific extensions
remain separately not evaluable.
"""
from __future__ import annotations

import re

import numpy as np

from ..rules.signals import map_signals

# Source row order: WG-3 table 5, pp.28-29. None means no canonical mapper.
DISTANCE = [
    ('Zone 1 pickup', 'Z1'), ('Zone 2 pickup', 'Z2'), ('Zone 3 pickup', 'Z3'),
    ('Zone 4 reverse pickup', None), ('Zone 1 trip', None), ('Zone 2 trip', 'TRIP_Z2'),
    ('Zone 3 trip', 'TRIP_Z3'), ('Zone 4 reverse trip', None),
    ('Carrier aided zone trip', None), ('AR block', 'AR_BLOCK'), ('CB ready', 'CB_READY'),
    ('AR start', 'AR_INITIATE'), ('AR close command', 'AR_CLOSE'), ('AR unsuccessful', 'AR_FAIL'),
    ('AR switch out', None), ('SOTF initiation', None), ('SOTF operated', None),
    ('VT fuse fail', 'VT_FAIL'), ('Broken conductor', 'BROKEN_CONDUCTOR'),
    ('Power swing block', None), ('Carrier unhealthy/fail', 'CARRIER_FAIL'),
    ('Carrier switch out', None), ('Carrier send', 'CARRIER_SEND'), ('Carrier receive', 'CARRIER_RECV'),
    ('DT send', None), ('DT receive', None), ('CB close', None), ('CB open', None),
    ('86 relay operated', 'LOCKOUT_86'), ('Main2/backup relay/BCU fail', None),
    ('Time synchronization status', 'TIME_SYNC_FAIL'), ('LAN network status', 'LAN_FAIL')]

# Table 11, pp.31-32: individual pole trips/positions cannot be replaced by one general bit.
DISTANCE_220 = [('Trip R phase', 'TRIP_A'), ('Trip Y phase', 'TRIP_B'), ('Trip B phase', 'TRIP_C')] + DISTANCE[:26] + [
    ('Earth fault start', 'EF_PICKUP'), ('Earth fault operated', 'EF_TRIP'),
    ('CB R phase close', None), ('CB R phase open', 'CB_OPEN_A'),
    ('CB Y phase close', None), ('CB Y phase open', 'CB_OPEN_B'),
    ('CB B phase close', None), ('CB B phase open', 'CB_OPEN_C'),
    ('86 relay operated', 'LOCKOUT_86'), ('96 relay operated', None),
    ('Main2/Main1/BCU fail', None), ('Time synchronization status', 'TIME_SYNC_FAIL'), ('LAN network status', 'LAN_FAIL')]
DISTANCE_220[17] = ('AR switch in/out', None)
BACKUP_132 = [('Relay 3 phase trip', 'TRIP_3P'), ('Overcurrent R phase start', None),
              ('Overcurrent Y phase start', None), ('Overcurrent B phase start', None),
              ('Overcurrent operated', 'OC_TRIP'), ('Earth fault start', 'EF_PICKUP'),
              ('Earth fault operated', 'EF_TRIP'), ('CB open', None), ('CB close', None),
              ('86 operated', 'LOCKOUT_86'), ('96 operated', None), ('Main1 relay fail', None),
              ('Time synchronization status', 'TIME_SYNC_FAIL'), ('LAN network status', 'LAN_FAIL')]
PROFILES = {'wg3-132-distance': ('132 kV Main-1 distance', 5, 'pages 28-29', DISTANCE),
            'wg3-132-backup': ('132 kV Main-2 backup', 8, 'page 30', BACKUP_132),
            'wg3-220plus-distance': ('220 kV and above Main-1/Main-2 distance', 11, 'pages 31-32', DISTANCE_220)}


def _normal(name):
    return re.sub('[^A-Z0-9]', '', name.upper().replace('PHASE', 'PH').replace('Φ', 'PH'))


def recording_points(rec, profile):
    if profile not in PROFILES:
        return {'profile': profile, 'label': 'Recording profile not declared', 'points': [],
                'note': 'Select a WG-3 recording profile during assignment review; no voltage/function is inferred.'}
    label, table, pages, definitions = PROFILES[profile]
    mapped = map_signals(list(rec.digital), rec.notes.get('digital_overrides'))
    points = []
    for row, (title, canonical) in enumerate(definitions, 1):
        names = set(mapped.channels(canonical)) if canonical else set()
        overrides = rec.notes.get('digital_overrides', {})
        names.update(n for n in rec.digital if n not in overrides and _normal(n) == _normal(title))
        # Existing zone mapping can also contain a zone-qualified trip; it is
        # not evidence for the table's distinct zone-pickup point.
        if canonical in ('Z1', 'Z2', 'Z3'):
            names = {n for n in names if overrides.get(n) == canonical or 'TRIP' not in n.upper()}
        names = sorted(names)
        status = 'pass' if names else 'gap' if canonical else 'not_evaluable'
        actual = 'mapped point recorded' if names else 'not recorded / unmapped' if canonical else 'no supported semantic match'
        if names and (any(len(rec.digital[n]) != rec.n or not np.all(np.isin(rec.digital[n], [0, 1])) for n in names)
                      or len(names) > 1):
            status, actual = 'not_evaluable', 'multiple candidate points or invalid samples; mapping review required'
        points.append({'id': f'WG3-T{table}-{row:02d}', 'title': title, 'status': status,
                       'expected': 'point recorded in this profile', 'actual': actual,
                       'channels': names, 'canonical': canonical, 'source_id': 'fold-wg3-final-report',
                       'source': f'FOLD WG-3 (2023), table {table}, row {row}, {pages}',
                       'action': 'Confirm the channel identity/configuration against the controlled relay export.'})
    return {'profile': profile, 'label': label, 'points': points,
            'note': 'Pass means mapped point coverage in this file, not healthy operation or verified wiring/configuration. '
                    'Conditional tables 6/9/12/13 and bay-specific additions still require review.'}
