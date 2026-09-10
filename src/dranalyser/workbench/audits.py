"""Attach recording/settings checklists to every supplied record."""
from ..comtrade.parser import read_cff, read_comtrade
from ..standards.checklist import relay_checklist


def audit_bundle(bundle, records, settings, bindings):
    out = []
    for f in bundle.records():
        rec = records.get(f.name)
        reason = f.error or 'Record could not be read.'
        try:
            if rec is None and f.ok:
                path = bundle.root + '/' + f.name
                rec = (read_cff(path, channel_mapping=f.channel_mapping) if f.name.lower().endswith('.cff')
                       else read_comtrade(path, channel_mapping=f.channel_mapping))
            row = relay_checklist(rec, settings.get(f.name), bindings[f.name],
                                  getattr(f, 'recording_profile', 'unconfirmed'), reason)
        except Exception as exc:
            # An advisory audit failure must not erase successful fault analysis.
            row = {'error': type(exc).__name__ + ': ' + str(exc)[:200], 'scope': 'Audit unavailable; no compliance conclusion.'}
        row.update(file=f.name, end=f.terminal_end, protection_system=f.protection_system,
                   role=f.role, blocked=f.blocked or bool(rec and rec.blocked()))
        row['quality_flags'] = sorted(set(row.get('quality_flags', []) + f.flags))
        out.append(row)
    return out
