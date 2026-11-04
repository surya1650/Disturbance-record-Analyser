"""Published line constants offered for explicit incident input review.

This catalogue is independent of the line registry. A reference identifies a
published conductor/circuit description, never the physical line in a record.
No voltage-based default or automatic match is provided.
"""
from copy import deepcopy


LINE_REFERENCE_CATALOGUE_VERSION = 1
LINE_REFERENCE_CATALOGUE_ID = 'published-line-references-2026-11-04'

_ERPC_31_MINUTES_URL = 'https://erpc.gov.in/wp-content/uploads/2016/08/145216645131ERPCTCCMINUTES.pdf'
_ERPC_31_DOWNLOAD_URL = (
    'https://www.erpc.gov.in/meetings/multiple-document/download/'
    'eyJpdiI6IlFXVnViRlNVbTBnb1ppVVQrcFcrZ3c9PSIsInZhbHVlIjoieDl1bnNTdjRxcTdrdUJ0TW9VYzN5dz09'
    'IiwibWFjIjoiNTc4NWNmODJlM2Y1ZDdjZDQxNDg4ZWRhZmIyMTc0NGYxMjYzYWE5NWY0MTg3NDg3ODRlYWM2'
    'MWY2M2RlY2YxYyIsInRhZyI6IiJ9'
)

_REFERENCES = ({
    'id': 'erpc-2015-powergrid-panther-132-sc',
    'label': '132 kV Single Panther, single circuit — Powergrid 4 Nov 2015 / ERPC reference',
    'kv': 132.0,
    'conductor': 'Single Panther',
    'circuit_configuration': 'single-circuit',
    'circuit_count': 1,
    'basis': 'per-km',
    'units': 'ohm/phase/km (primary)',
    'parameters': {'r1': 0.1622, 'x1': 0.3861, 'r0': 0.4056, 'x0': 1.622},
    'reference_only': True,
    'is_standard': False,
    'requires_applicability_review': True,
    'measured_for_incident_line': False,
    'conditions': {
        'frequency_hz': None,
        'conductor_temperature_c': None,
        'tower_geometry': None,
        'earth_resistivity_ohm_m': None,
        'transposition': None,
    },
    'source': {
        'publisher': 'Eastern Regional Power Committee, Ministry of Power, Government of India',
        'title': 'Minutes of the 31st ERPC and TCC meetings',
        'edition': 'Meetings of 13–14 November 2015; circulated 6 January 2016',
        'url': _ERPC_31_MINUTES_URL + '#page=39',
        'alternate_url': _ERPC_31_DOWNLOAD_URL + '#page=39',
        'listing_url': 'https://www.erpc.gov.in/erpc?page=4',
        'locator': '31st ERPC minutes, item E1, printed page 36; Powergrid email of 4 November 2015, final row',
        'printed_page': 36,
        'pdf_page': 39,
        'units_context': 'The preceding line-parameter table on printed page 35 labels impedance in ohm/phase/km.',
        'checked_on': '2026-11-04',
    },
    'applicability': (
        'Published general reference for the stated conductor and circuit; use measured or approved '
        'line-specific data when available. An engineer must review its applicability before use.'
    ),
    'limitations': [
        'These published reference values are not measurements or approved constants for the incident line.',
        'Frequency, conductor temperature, tower geometry, earth resistivity and transposition are not stated in this table.',
        'The same minutes give different Single Panther single-circuit values in an earlier PCC table; '
        'the conductor name alone does not resolve which applies.',
        'This entry does not establish actual conductor, configuration, line length, terminal identity or event pairing.',
        'For other conductors, circuits, mixed sections or uncertain conditions, enter measured or approved values manually.',
    ],
},)


def list_line_references():
    """Return independent JSON-safe reference rows; none is selected by default."""
    return deepcopy(list(_REFERENCES))


def get_line_reference(reference_id):
    """Look up an explicit catalogue ID, leaving unknown selections unavailable."""
    return next((deepcopy(row) for row in _REFERENCES if row['id'] == reference_id), None)


def line_reference_catalogue():
    """Serialize publication provenance and the manual fallback for a reader UI."""
    return {
        'version': LINE_REFERENCE_CATALOGUE_VERSION,
        'catalogue_id': LINE_REFERENCE_CATALOGUE_ID,
        'selection_policy': 'explicit-only',
        'default_reference_id': None,
        'manual_entry_available': True,
        'manual_entry_guidance': (
            'Prefer measured or approved line-specific constants. If no applicable published reference '
            'is available, supply the conductor/configuration and impedance evidence manually.'
        ),
        'references': list_line_references(),
    }


def reference_line_review(reference_id):
    """Provide an unconfirmed positive-sequence draft after an explicit choice.

    Length, section geometry, end choices and confirmations remain manual.
    Callers must not preserve numeric zero-sequence inputs across a change of
    impedance basis: refuse that change until their units are explicitly resolved.
    """
    row = get_line_reference(reference_id)
    if row is None:
        raise ValueError('Published line reference is unavailable; enter approved values manually.')
    return {
        'kv': row['kv'],
        'basis': row['basis'],
        'r1': row['parameters']['r1'],
        'x1': row['parameters']['x1'],
        'reference_id': row['id'],
        'reference_reviewed': False,
        'evidence': row['source']['locator'] + '. ' + row['source']['url']
            + ' General reference only; engineering applicability review required.',
    }
