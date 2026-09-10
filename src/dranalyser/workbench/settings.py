"""Associate settings by record location; never assign exports by iteration order."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import hashlib

from ..registry.settings_io import load_settings


def settings_by_record(bundle, names):
    """One export per record, using exact stem or an unambiguous folder.

    File association is not proof of device identity or event-time validity.
    Never lend a primary relay's export to its same-terminal corroborator.
    """
    candidates, settings, errors = {}, {}, []
    info = {n: {'status': 'not supplied', 'file': '', 'reason': 'No uniquely associated settings export.',
                'effective_at_event': 'unconfirmed', 'warnings': [], 'unsupported_files': []} for n in names}
    for sf in bundle.settings():
        if not sf.name.lower().endswith('.rio'):
            for n in names:
                if PurePosixPath(n).is_relative_to(PurePosixPath(sf.name).parent):
                    info[n]['unsupported_files'].append(sf.name)
            continue
        export = PurePosixPath(sf.name)
        exact = [n for n in names if PurePosixPath(n).parent == export.parent
                 and PurePosixPath(n).stem.casefold() == export.stem.casefold()]
        matches = exact or [n for n in names if PurePosixPath(n).is_relative_to(export.parent)]
        if len(matches) != 1:
            reason = sf.name + ': settings terminal is ambiguous or relay identity is unresolved; use separate relay folders or matching stems'
            errors.append(reason)
            for n in matches:
                info[n]['warnings'].append(reason)
            continue
        candidates.setdefault(matches[0], []).append(sf)
    for name, exports in candidates.items():
        if len(exports) != 1:
            reason = name + ': multiple settings exports; no version selected'
            errors.append(reason)
            info[name].update(status='ambiguous', reason=reason)
            continue
        sf = exports[0]
        try:
            settings[name] = load_settings(str(Path(bundle.root) / sf.name))
            provenance = getattr(settings[name], 'provenance', None)
            path = Path(bundle.root) / sf.name
            info[name].update(status='associated export', file=sf.name,
                              reason='Associated by filename/folder; relay identity and effective date need confirmation.',
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else '',
                              format=getattr(provenance, 'fmt', ''),
                              importer=getattr(provenance, 'importer', ''),
                              unknown_fields=list(getattr(settings[name], 'unknown', [])))
            info[name]['warnings'].extend(getattr(provenance, 'warnings', []))
        except Exception as exc:
            reason = sf.name + ': ' + str(exc)[:200]
            errors.append(reason)
            info[name].update(status='unreadable or unsupported', file=sf.name, reason=reason)
    for value in info.values():
        if value['status'] == 'not supplied' and value['warnings']:
            value.update(status='ambiguous', reason='No uniquely associated export; see association warnings.')
        elif value['status'] == 'not supplied' and value['unsupported_files']:
            value.update(status='unsupported format', reason='Other export files are present; this association path imports RIO only.')
    return settings, info, errors


def settings_for(bundle, used):
    names = sorted({f.name for f in bundle.records()} | set(used.values()))
    settings, _, errors = settings_by_record(bundle, names)
    return {end: settings[name] for end, name in used.items() if name in settings}, errors
