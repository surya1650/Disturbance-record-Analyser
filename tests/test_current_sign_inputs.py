"""Unknown recording polarity stays gated; existing confirmed sign facts are reused."""
import copy

import pytest

from dranalyser.workbench.incident_inputs import incident_line_missing, incident_line_model
from tests.test_incident_inputs import metadata_and_bundle


def test_missing_sign_names_the_actual_setup_fact_without_guessing_direction():
    _, metadata, bundle = metadata_and_bundle()
    review = metadata['incident_line']['review']
    for end in review['ends'].values():
        end['current_direction'] = 'unknown'
    original = copy.deepcopy(metadata)
    missing = incident_line_missing(metadata['incident_line'])
    assert len(missing) == 2
    assert all('recorded sign convention in Setup' in item for item in missing)
    assert all('not power-flow direction' in item for item in missing)
    with pytest.raises(ValueError, match='Confirm S current direction'):
        incident_line_model(metadata, bundle)
    assert metadata == original


def test_existing_declared_bus_line_and_reverse_signs_need_no_new_wiring_fields():
    _, metadata, bundle = metadata_and_bundle()
    review = metadata['incident_line']['review']
    review['ends']['R']['current_direction'] = 'line-to-bus'
    original = copy.deepcopy(metadata)
    model = incident_line_model(metadata, bundle)
    assert model['terminals']['S']['i_polarity'] == 1
    assert model['terminals']['R']['i_polarity'] == -1
    assert not incident_line_missing(metadata['incident_line'])
    assert metadata == original
    assert all('ct_wiring' not in end for end in review['ends'].values())
