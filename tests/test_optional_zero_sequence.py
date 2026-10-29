"""Method-scoped inputs: E5 and phase loops must not demand unrelated Z0.

PROJECT_CONTEXT §7.2: E5 equates the terminal negative-sequence fault voltage
magnitudes using Z1 only. No estimator equation changes here: missing Z0 is
unknown, ground compensation is refused, and eligible phase loops ignore it.
"""
import copy
from types import SimpleNamespace

import pytest
import yaml

from dranalyser.application.worker import Worker
from dranalyser.cli.commands import cmd_locate
from dranalyser.faultloc.ensemble import locate
from dranalyser.faultloc.model_domain import scalar_model_reasons
from dranalyser.faultloc.sections import section_model_reasons
from dranalyser.ml.tier1 import apply_k0, estimate_k0
from dranalyser.registry.loader import line_from_dict
from scripts.create_demo import create_demo
from tests import test_application as fixtures
from tests.test_application import payload
from tests.test_ml import _incident

environment = fixtures.environment


def positive_only(line):
    return line_from_dict({'id': line.id, 'kv': line.kv,
        'sections': [{'from_km': s.from_km, 'to_km': s.to_km, 'r1': s.r1, 'x1': s.x1}
                     for s in line.sections],
        'terminals': {end: {'substation': t.substation, 'vt_type': t.it.vt_type}
                      for end, t in line.terminals.items()}})


@pytest.mark.parametrize('m', [.15, .42, .8])
@pytest.mark.parametrize('fault', ['AG', 'BG', 'AB', 'BC'])
def test_e5_needs_no_zero_sequence_or_source_impedances(m, fault):
    _, _, known, terms = _incident(m, fault, rf=3)
    expected = locate(known, terms)
    line = positive_only(known)
    assert line.z0 is None and line.sections[0].z0 is None
    assert line.terminals['S'].zs0 is None and line.terminals['R'].zs1 is None
    assert not scalar_model_reasons(line) and not section_model_reasons(line)
    for t in terms.values():
        t.zs1 = t.zs0 = None
    actual = locate(line, terms)
    assert actual.ok and actual.method == expected.method == 'E5'
    assert actual.km_from_S == pytest.approx(expected.km_from_S, abs=1e-10)
    assert actual.km_from_S == pytest.approx(m*line.length_km, abs=.5)
    if fault.endswith('G'):
        assert all(not e.ok and 'zero-sequence R0/X0' in e.reason for e in actual.estimates if e.ends == 'single')


@pytest.mark.parametrize('fault', ['AB', 'BC', 'CA'])
def test_single_ended_phase_loops_remain_eligible_without_compensation(fault):
    _, _, known, terms = _incident(.42, fault, rf=0)
    expected = locate(known, {'S': terms['S']})
    line = positive_only(known)
    actual = locate(line, {'S': terms['S']})
    assert actual.ok and actual.mode == 'single-ended'
    assert actual.km_from_S == pytest.approx(expected.km_from_S, abs=1e-10)
    assert any(e.ok and e.method.startswith('E1') for e in actual.estimates)
    assert any(e.ok and e.method.startswith('E2') for e in actual.estimates)
    assert all(not e.ok for e in actual.estimates if e.method.startswith('E3'))


def test_ground_single_ended_refuses_unknown_z0_and_e3_names_missing_source_data():
    _, _, known, terms = _incident(.42, 'AG', rf=3)
    line = positive_only(known)
    result = locate(line, {'S': terms['S']})
    assert not result.ok
    assert all(not e.ok and 'line zero-sequence R0/X0' in e.reason for e in result.estimates)
    line = copy.deepcopy(known)
    line.terminals['R'].zs0 = None
    terms['S'].zs0 = None
    result = locate(line, {'S': terms['S']})
    assert any(e.ok and e.method.startswith('E1') for e in result.estimates)
    e3 = next(e for e in result.estimates if e.method.startswith('E3'))
    assert not e3.ok and 'source zero-sequence impedances required at both ends' in e3.reason
    with pytest.raises(ValueError, match='zero-sequence R0/X0'):
        _ = positive_only(known).k0_line


@pytest.mark.parametrize('invalid', [float('nan'), float('inf'), -.1])
def test_declared_invalid_zero_sequence_remains_an_input_failure(invalid):
    _, _, known, _ = _incident(.42)
    line = positive_only(known)
    line.sections[0].r0 = invalid
    assert scalar_model_reasons(line) and section_model_reasons(line)


def test_tier1_never_invents_a_missing_zero_sequence_baseline():
    _, _, known, _ = _incident(.42)
    line = positive_only(known)
    with pytest.raises(ValueError, match='requires declared line zero-sequence'):
        estimate_k0([], line)
    with pytest.raises(ValueError, match='original line Z0'):
        apply_k0(line, SimpleNamespace(accepted=True))


def test_cli_positive_only_model_reports_missing_compensation_and_eligible_e5(tmp_path, capsys):
    demo = create_demo(tmp_path/'demo')
    path = demo/'synthetic-line.yaml'
    definition = yaml.safe_load(path.read_text())
    for section in definition['sections']:
        section.pop('r0')
        section.pop('x0')
    for terminal in definition['terminals'].values():
        terminal.pop('zs0')
        terminal.pop('zs1')
    path.write_text(yaml.safe_dump(definition))
    result = cmd_locate(SimpleNamespace(line=str(path), S=str(demo/'S/event.cfg'), R=str(demo/'R/event.cfg')))
    output = capsys.readouterr().out
    assert result == 0
    assert 'Z0 / ground-loop k0: Not supplied' in output
    assert 'E5' in output and '41.988' in output


def test_mixed_positive_only_sections_keep_existing_section_solver_and_chainage():
    from dranalyser.dsp.pipeline import analyse
    from dranalyser.faultloc.ensemble import TerminalInput
    from tests.source_fault_records import records
    from tests.test_model_domain import definition
    from tests.test_source_fault_oracle import SECTIONS

    line = positive_only(definition(SECTIONS))
    line.section_solver_enabled = True
    pair = records(SECTIONS, 75, 'AG')
    result = locate(line, {end: TerminalInput(analyse(rec), end) for end, rec in pair.items()})
    assert result.ok and result.method == 'E5-sections'
    assert result.km_from_S == pytest.approx(75, abs=.05)
    assert line.z0 is None


def test_positive_only_worker_result_is_persisted_and_source_bound(environment):
    client, app, source, registry = environment
    path = registry/'demo.yaml'
    declaration = yaml.safe_load(path.read_text())
    for section in declaration['sections']:
        section.pop('r0')
        section.pop('x0')
    for terminal in declaration['terminals'].values():
        terminal.pop('zs0')
        terminal.pop('zs1')
    path.write_text(yaml.safe_dump(declaration))
    response = client.post('/api/intake', files=payload(source)+payload(source, 'R'),
                          data={'metadata': (source/'intake.json').read_text()})
    assert response.status_code == 202
    identity = response.json()['incident_id']
    assert Worker(app.state.store, registry).once()
    row = app.state.store.get(identity)
    assert row['state'] == 'completed', row['error']
    summary = row['result']['location_summary']
    assert summary['status'] == 'accepted' and summary['method'] == 'E5'
    assert summary['km_from_S'] == pytest.approx(41.988, abs=.001)
    assert summary['source_records'] == {'S': 'S/event.cfg', 'R': 'R/event.cfg'}
    assert summary['binding']['files_sha256'] == {f['name']: f['sha256'] for f in row['files']}
    assert summary['binding']['revision'] == row['number']
    assert all(not e['accepted'] and 'zero-sequence' in e['reason']
               for e in summary['estimates'] if e['ends'] == 'single')
