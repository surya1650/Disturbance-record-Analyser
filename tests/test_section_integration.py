"""Real DSP/window/review objects with independently solved sequence inputs.

Phasor replacement isolates section dispatch; it is not waveform acquisition QA.
"""
import copy
from dataclasses import asdict
import datetime as dt

import numpy as np
import pytest

from dranalyser.dsp.stage_windows import stage_window
from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc.ensemble import TerminalInput, locate
from dranalyser.faultloc.stage_location import stage_e5
from dranalyser.registry.loader import line_from_dict
from dranalyser.signals import AnalogMeta, Record
from dranalyser.workbench.stage_location import stage_locations
from tests.test_model_domain import MIXED, definition
from tests.test_section_solver import quantities
from tests.test_stage_location import reviewed_pair
from tests.section_network_oracle import solve


@pytest.fixture(scope='module')
def dsp_pair():
    return reviewed_pair()


def prepared(dsp_pair, rotation=0, aligned=False):
    ans, rows = copy.deepcopy(dsp_pair)
    line = definition(MIXED)
    line.section_solver_enabled = True
    q = quantities(MIXED, 75, rotation=rotation)
    terms = {}
    for i, end in enumerate(('S', 'R')):
        an = ans[end]
        an.ps.phasors['V2'][:] = q[2*i]
        an.ps.phasors['I2'][:] = q[2*i+1]
        an.fault_type = 'AG'
        an.saturation.detected = False
        an.window.t_start, an.window.t_end = stage_window(an, rows[i]['stages']['intervals'][0])['window_s']
        terms[end] = TerminalInput(an, end, clock_good=aligned)
    return line, ans, rows, terms


@pytest.mark.parametrize('aligned,rotation', [(True, 0), (False, 0), (False, 1.7)])
def test_enabled_main_solver_reports_physical_chainage_without_scalar_blend_or_towers(dsp_pair, aligned, rotation):
    line, _, _, terms = prepared(dsp_pair, rotation, aligned)
    result = locate(line, terms)
    assert result.ok and result.mode == 'two-ended', result
    assert result.km_from_S == pytest.approx(75, abs=1e-7)
    assert result.m == pytest.approx(34.5/52, abs=1e-10)
    assert result.km_from_R == pytest.approx(25, abs=1e-7)
    assert result.method == ('E4-sections' if aligned else 'E5-sections')
    assert all(e.ends == 'two' for e in result.estimates)
    assert not result.towers and result.likely_tower is None
    assert result.diagnostics['section_solver']['status'] == 'located'
    assert '75.000' in result.table()


@pytest.mark.parametrize('problem', ['disabled', 'review', 'coupling', 'capacitor', 'shunt', 'missing',
                                   'weak', 'saturated', 'clipped', 'balanced', 'polarity', 'nonfinite', 'bad opt in'])
def test_main_section_guards_withhold_without_fallback(dsp_pair, problem):
    line, ans, _, terms = prepared(dsp_pair)
    if problem == 'disabled':
        line.section_solver_enabled = False
    elif problem == 'bad opt in':
        line.section_solver_enabled = 'true'
    elif problem == 'review':
        line.model_review_required = True
    elif problem == 'coupling':
        line.double_circuit = True
    elif problem == 'capacitor':
        line.series_compensated = True
    elif problem == 'shunt':
        line.sections[0].b1 = 1e-6
    elif problem == 'missing':
        terms.pop('R')
    elif problem == 'weak':
        ans['R'].ps.phasors['I2'][:] = 0
    elif problem == 'saturated':
        ans['S'].saturation.detected = True
    elif problem == 'clipped':
        ans['S'].clipping = ['IA']
    elif problem == 'balanced':
        for an in ans.values():
            an.fault_type = 'ABC'
    elif problem == 'polarity':
        terms['R'].polarity = 0
    else:
        ans['R'].ps.phasors['V2'][:] = np.nan
    result = locate(line, terms)
    assert not result.ok and np.isnan(result.km_from_S) and not result.towers, result
    assert result.likely_tower is None and result.caveats


def test_reviewed_stages_dispatch_enabled_solver_and_retain_review_permission(dsp_pair):
    line, ans, rows, _ = prepared(dsp_pair, 1.3)
    results = stage_locations(line, ans, rows, {'S': 'S.cfg', 'R': 'R.cfg'})
    assert results[0]['status'] == 'located', results
    assert results[0]['km_from_S'] == pytest.approx(75, abs=1e-7)
    assert results[0]['method'] == 'E5-sections' and not results[0]['clock_shift_applied']
    rows[0]['stages']['review']['location_requested'] = False
    assert all(r['status'] == 'withheld' for r in stage_locations(line, ans, rows, {'S':'S.cfg', 'R':'R.cfg'}))


@pytest.mark.parametrize('problem', ['review', 'disabled', 'weak', 'short', 'polarity', 'balanced'])
def test_stage_section_guards_preserve_existing_screens(dsp_pair, problem):
    line, ans, rows, _ = prepared(dsp_pair)
    stages = [r['stages']['intervals'][0] for r in rows]
    polarity = 1
    if problem == 'review':
        line.model_review_required = True
    elif problem == 'disabled':
        line.section_solver_enabled = False
    elif problem == 'weak':
        ans['R'].ps.phasors['I2'][:] = 0
    elif problem == 'short':
        stages[0]['end_s'] = stages[0]['start_s']+.025
    elif problem == 'balanced':
        stages[0]['phase_pattern'] = 'ABC'
    else:
        polarity = 0
    result = stage_e5(line, ans['S'], ans['R'], *stages, polarity_r=polarity)
    assert result['status'] == 'withheld' and result['km_from_S'] is None


@pytest.mark.parametrize('value', ['true', 'false', 1, 0, None, []])
def test_registry_cannot_enable_section_solver_with_truthy_nonboolean(value):
    data = asdict(definition(MIXED))
    data['section_solver_enabled'] = value
    with pytest.raises(ValueError, match='boolean'):
        line_from_dict(data)


def test_registry_defaults_to_scalar_refusal_and_preserves_review_gate():
    data = asdict(definition(MIXED))
    data.pop('section_solver_enabled', None)
    assert line_from_dict(data).section_solver_enabled is False
    data.update(section_solver_enabled=True, model_review_required=True)
    result = line_from_dict(data)
    assert result.section_solver_enabled is True and result.model_review_required is True


@pytest.mark.parametrize('km,rotation', [(25, 0), (75, 1.3)])
def test_phase_nodal_sinusoidal_records_pass_through_actual_dsp_and_section_dispatch(km, rotation):
    """No phasor replacement: steady sinusoidal states, not an EMT model."""
    quiet, fault = solve(MIXED, km, resistance=1e12), solve(MIXED, km)
    terms = {}
    for end, fs, pre in [('S', 2400, .12), ('R', 1200, .173)]:
        t = np.arange(round((pre+.5)*fs))/fs
        physical = t-pre
        analog = {}
        for kind in ('V', 'I'):
            phasors = np.where(physical[None, :] < 0, quiet[kind+end][:, None], fault[kind+end][:, None])
            wave = np.sqrt(2)*np.real(phasors*np.exp(1j*(2*np.pi*50*physical+(rotation if end == 'R' else 0))))
            analog.update({kind+phase: wave[i] for i, phase in enumerate('ABC')})
        start = dt.datetime(2026, 10, 23)+dt.timedelta(seconds=1418 if end == 'R' else 0)
        rec = Record('nodal-'+end, 'SYNTHETIC', 'Main-1', '2013', start, start+dt.timedelta(seconds=pre),
                     fs, 50, t, analog, {}, terminal_end=end, time_basis='synthetic')
        rec.analog_meta = {k: AnalogMeta(k, 'A' if k[0] == 'I' else 'V', 1, 0, 1, 1, 'P', -1e9, 1e9,
                                       normalised=True) for k in analog}
        terms[end] = TerminalInput(analyse(rec), end)
    line = definition(MIXED)
    line.section_solver_enabled = True
    result = locate(line, terms)
    assert result.ok, result
    assert result.km_from_S == pytest.approx(km, abs=.05)
    assert not result.towers
