"""Evidence for a symbolic two-terminal incident line view, without new physics."""
import copy
import math
from pathlib import PurePosixPath

from .location_summary import binding_reason

_TRIP = {'TRIP', 'TRIP_A', 'TRIP_B', 'TRIP_C', 'TRIP_3P', 'TRIP_Z2', 'TRIP_Z3',
         'TRIP_Z4', 'OC_TRIP', 'EF_TRIP', 'DEFINITIVE_TRIP'}
_FEEDBACK = {'CB_OPEN_A', 'CB_OPEN_B', 'CB_OPEN_C', 'ANY_POLE_DEAD', 'ALL_POLE_DEAD'}


def _finite(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def _name(value):
    return str(value) if value and value != 'Not available' else None


def _observations(source, meanings):
    observations = []
    for event in (source.get('digital') or {}).get('events', []):
        roles = {value.strip() for value in str(event.get('meaning') or '').split(',')}
        if not roles & meanings:
            continue
        bounds = event.get('source_bracket_s')
        bracket = (list(bounds) if isinstance(bounds, (list, tuple)) and len(bounds) == 2
                   and all(_finite(value) is not None for value in bounds) else None)
        observations.append(dict(signal=str(event.get('plain_label') or event.get('label') or 'Recorded indication'),
            meaning=str(event.get('meaning') or ''), kind=str(event.get('kind') or 'state change'),
            source_s=_finite(event.get('source_s')), source_bracket_s=bracket,
            assertion_source=event.get('assertion_source'),
            polarity_reviewed=event.get('assertion_source') == 'source-analysis choice',
            interpretation_available=event.get('interpretation_available') is True,
            transition_time_known=event.get('kind') != 'state difference across gap'))
    return observations[:4], max(0, len(observations)-4)


def _source_at_end(revision, facts, sources, end):
    result = revision.get('result') or {}
    if binding_reason(result.get('location_summary'), revision, facts.get('sha256')):
        return None
    record = (result.get('used') or {}).get(end)
    source = next((source for source in sources if source.get('record') == record), None)
    if source is None:
        return None
    inventory = {item['name']: item for item in (revision.get('bundle') or {}).get('files', [])}
    item = inventory.get(record) or {}
    if item.get('terminal_end') != end or item.get('role') != 'primary':
        return None
    names = [record] + ([item['data_file']] if item.get('data_file') else [])
    files = {item['name']: item['sha256'] for item in revision.get('files', [])}
    expected = {PurePosixPath(name).name: files[name] for name in names if name in files}
    if not expected or len(expected) != len(names) or expected != source.get('source_sha256'):
        return None
    return source


def build_line_diagram(revision, facts, sources, location):
    """Attach declared geometry and already eligible km; never interpret CB motion."""
    length = _finite(facts.get('length_km'))
    length = length if length is not None and length > 0 else None
    line = dict(id=_name(facts.get('id')), name=_name(facts.get('name')),
        kv=_finite(facts.get('kv')), length_km=length, sha256=facts.get('sha256'),
        parameter_status=facts.get('parameter_status'), provenance=facts.get('provenance'))
    terminals = {}
    for end in ('S', 'R'):
        source = _source_at_end(revision, facts, sources, end)
        trips, omitted_trips = _observations(source or {}, _TRIP)
        feedback, omitted_feedback = _observations(source or {}, _FEEDBACK)
        terminals[end] = dict(end=end,
            label=_name((facts.get('terminals') or {}).get(end)) or 'End '+end+' (name unavailable)',
            record=source['record'] if source else None,
            source_sha256=copy.deepcopy(source.get('source_sha256') or {}) if source else {},
            breaker=dict(state='unknown', label='CB '+end,
                reason='Physical breaker position is not established by this schematic or recorded commands.',
                trip_observations=trips, feedback_observations=feedback,
                omitted_trip_observations=omitted_trips, omitted_feedback_observations=omitted_feedback))
    km, remote = _finite(location.get('km_from_S')), _finite(location.get('km_from_R'))
    result = revision.get('result') or {}
    used = result.get('used') or {}
    bound_cohort = (bool(used) and set(used.values()) == {source.get('record') for source in sources}
        and not binding_reason(result.get('location_summary'), revision, facts.get('sha256'))
        and all(end in terminals and terminals[end]['record'] == record for end, record in used.items()))
    eligible = (location.get('status') == 'Existing conditional estimate' and location.get('reference') == 'S'
        and bound_cohort
        and isinstance(location.get('method'), str) and bool(location['method'].strip())
        and facts.get('sha256') is not None
        and location.get('line_sha256') == facts.get('sha256') and length is not None
        and km is not None and remote is not None and 0 <= km <= length and 0 <= remote <= length
        and math.isclose(km+remote, length, rel_tol=1e-9, abs_tol=1e-9))
    reason = (location.get('reason') or 'An eligible method-labelled physical fault distance is unavailable.')
    if not eligible and km is not None:
        reason = 'Fault marker withheld: stored distance, model length or source eligibility is inconsistent.'
    fault = dict(status='eligible' if eligible else 'unavailable',
        method=location.get('method') if eligible else None,
        km_from_S=km if eligible else None, km_from_R=remote if eligible else None,
        position_fraction=km/length if eligible else None, reason=reason)
    return dict(version=1, status='declared line schematic' if facts.get('sha256') else 'generic schematic',
        line=line, terminals=terminals, fault=fault,
        connections=dict(status='not supplied',
            note='Only the modelled two-terminal circuit is shown; other connected lines are not supplied.'),
        notes=['CB symbols are schematic terminal switching points; physical bay arrangement and breaker positions are unverified.',
            'Distances follow the frozen line model and existing method-labelled result; this view does not calculate a new location.',
            'Recorded indications retain each source local clock; a command or pole indication alone does not confirm mechanical operation.'])
