"""Application-facing advisory audits with source and applicability limits."""
from __future__ import annotations

from dataclasses import asdict

from .audit import audit_record, audit_settings
from .catalogue import load_catalogue, load_sources
from .recording import recording_points


def pending(check_id, title, expected, actual, source):
    return dict(id=check_id, title=title, status='not_evaluable', expected=expected,
                actual=actual, source=source, action='Review the controlled configuration and supporting evidence.')


def summary(checks):
    counts = {s: sum(c['status'] == s for c in checks) for s in ('pass', 'gap', 'not_evaluable')}
    return dict(counts, status='GAP' if counts['gap'] else 'INCOMPLETE' if counts['not_evaluable'] else 'PASS')


def reference_pack():
    """Only the configured recording/philosophy pack; TB guidance is not a compliance check."""
    ids = {'fold-wg3-final-report', 'aptransco-general-philosophy',
           'aptransco-distance-review-2024', 'load-encroachment-workbook'}
    return [{k: s.get(k, '') for k in ('id', 'title', 'document_date', 'sha256')}
            for s in load_sources() if s['id'] in ids]


def relay_checklist(rec, settings, binding, profile='unconfirmed', unavailable_reason=''):
    recording = ([asdict(c) for c in audit_record(rec).checks if c.id != 'DR-DIGITAL'] if rec is not None else
                 [pending('DR-READ', 'Recording evidence', 'Readable COMTRADE', unavailable_reason, 'COMTRADE intake')])
    points = (recording_points(rec, profile) if rec is not None else
              {'profile': profile, 'label': 'Recording unavailable', 'points': [], 'note': unavailable_reason})
    if profile == 'unconfirmed':
        recording.append(pending('DR-PROFILE', 'Reference-table applicability', 'Declared voltage/function profile',
                                 'No recording profile declared; no voltage or function inferred.', 'FOLD WG-3, pages 28-32'))
    recording.append(pending('DR-CONFIG', 'Complete recorder configuration',
                             'Trigger logic, channel capacity, topology and conditional points',
                             'A captured file does not prove the full recorder configuration, parallel-line or tie-breaker inputs.',
                             'FOLD WG-3, pages 10-11 and tables 4/6/9/10/12/13, pages 28-33'))
    # Current registry ratios are terminal-scoped and unverified. They must not
    # be lent to every Main-1/Main-2 CT core to claim a verified primary reach.
    setting_checks = [asdict(c) for c in audit_settings(settings, None).checks]
    if settings is None:
        setting_checks.extend(pending(key, title, 'Associated settings export', 'No usable settings export.',
                                      'APTRANSCO general philosophy and revised review (27 Nov 2024)')
                              for key, title in [('SET-Z1', 'Zone 1 reach'), ('SET-Z2-TIME', 'Z2 time delay'),
                                                 ('SET-Z3-TIME', 'Z3 time delay'), ('SET-REVERSE', 'Reverse zone'),
                                                 ('SET-K0', 'Compensation parameters'), ('SET-RLD', 'Load encroachment')])
    for c in setting_checks:
        if c['id'] == 'SET-Z1':
            c['actual'] = 'Verified line constants and per-relay CT/VT ratios are not supplied to this audit.'
        if c['id'] in ('SET-Z2-TIME', 'SET-Z3-TIME'):
            c['title'] += ' (minimum-delay screen only)'
        if c['id'] == 'SET-REVERSE':
            c['expected'] += '; +/-0.03 s is a project screening tolerance'
    setting_checks.extend([
        pending('SET-VALIDITY', 'Settings identity and event-time validity', 'Confirmed relay and effective settings version',
                binding.get('reason', 'Settings not supplied'), 'Operator/collector evidence; APTRANSCO reference applicability'),
        pending('SET-COORDINATION', 'Full zone reach and scheme coordination', 'Verified topology, adjacent-line data and per-relay ratios',
                'Minimum-delay and parameter-availability screens do not establish coordinated or enabled protection.',
                'APTRANSCO general philosophy, pages 1-2; revised review (27 Nov 2024), pages 1-2')])
    guidance = [pending(c['id'], c['summary'], 'Review the controlled source for the applicable scheme',
                        'Not automatically evaluated; required configuration fields or logic are unsupported.',
                        c['source_id'] + ', ' + c['locator'])
                for c in load_catalogue() if c['source_id'].startswith('aptransco-')
                and 'line' in c['asset_types'] and c['analyzer_state'] == 'catalogued']
    return {'recording_checks': recording, 'digital_profile': points, 'settings_checks': setting_checks,
            'guidance': guidance, 'settings_source': binding,
            'recording_summary': summary(recording + points['points']),
            'settings_summary': summary(setting_checks + guidance),
            'quality_flags': [str(f) for f in rec.flags] if rec is not None else [],
            'scope': 'Advisory reference-pack checks. Pass means only the stated evidence check passed; '
                     'gaps are not proof of incorrect protection operation or TB 854 noncompliance.'}
