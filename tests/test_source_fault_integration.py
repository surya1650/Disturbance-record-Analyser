"""Independent source/fault sinusoidal records through actual guarded DSP."""
import importlib

import numpy as np
import pytest

from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc.ensemble import TerminalInput, locate
from tests.test_model_domain import definition
from tests.test_source_fault_oracle import SECTIONS


@pytest.mark.parametrize('fault', ['AG', 'BG', 'CG', 'AB', 'BC', 'CA', 'ABG', 'BCG', 'CAG'])
def test_actual_dsp_additional_connections_locate_without_phasor_replacement(fault):
    records = importlib.import_module('tests.source_fault_records').records(SECTIONS, 75, fault)
    line = definition(SECTIONS)
    line.section_solver_enabled = True
    terms = {end: TerminalInput(analyse(rec), end) for end, rec in records.items()}
    result = locate(line, terms)
    assert result.ok and result.km_from_S == pytest.approx(75, abs=.05), result
    assert result.method == 'E5-sections' and not result.towers


@pytest.mark.parametrize('fault', ['ABC', 'ABCG'])
def test_balanced_connection_controls_do_not_enable_section_location(fault):
    records = importlib.import_module('tests.source_fault_records').records(SECTIONS, 75, fault)
    line = definition(SECTIONS)
    line.section_solver_enabled = True
    result = locate(line, {end: TerminalInput(analyse(rec), end) for end, rec in records.items()})
    assert not result.ok and np.isnan(result.km_from_S) and not result.towers


def test_complete_guarded_matrix_includes_every_profile_and_fault():
    result = importlib.import_module('scripts.source_fault_validation').guarded_cases()
    assert result['main']['planned'] == result['stage']['planned'] == 88
    for mode in ('main', 'stage'):
        assert result[mode]['located']+result[mode]['refused'] == 88
        assert result[mode]['unbalanced']['located'] >= 9
        assert result[mode]['unbalanced']['max_error_km'] < .05
        assert result[mode]['balanced_controls']['located'] == 0
