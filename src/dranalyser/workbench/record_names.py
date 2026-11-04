"""Editable display names from source evidence, never physical end assignments."""
import re
from pathlib import PurePosixPath

_GENERIC = re.compile(r'^(?:event|record|capture|disturbance|fault|dr)[ _-]*\d*$', re.I)
_HEADER = re.compile(r'^(?:unknown|station|substation|relay|micom|csc\d+[a-z]*)$', re.I)


def record_display_name(filename, *, station='', explicit=''):
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()[:200]
    path = PurePosixPath(str(filename).replace('\\', '/'))
    name = re.sub(r'[_\s]+', ' ', path.stem).strip()
    if name and not _GENERIC.fullmatch(name):
        return name[:200]
    folder = re.sub(r'[_\s]+', ' ', path.parent.name).strip()
    if folder and not _GENERIC.fullmatch(folder):
        return folder[:200]
    if isinstance(station, str) and station.strip() and not _HEADER.fullmatch(station.strip()):
        return station.strip()[:200]
    return name[:200] or 'Recording'


def saved_display_name(revision, filename, *, station='', explicit=''):
    if not explicit:
        choice = (revision.get('metadata') or {}).get('assignments', {}).get(filename) or {}
        explicit = choice.get('display_name') or ''
    line = (revision.get('metadata') or {}).get('incident_line') or {}
    for end in (line.get('review') or {}).get('ends', {}).values():
        if not explicit and end.get('record') == filename:
            explicit = end.get('name') or ''
    return record_display_name(filename, station=station, explicit=explicit)
