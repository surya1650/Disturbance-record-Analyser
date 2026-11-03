"""Rule findings preserve observations without inventing settings compliance."""
import numpy as np
import pytest

from dranalyser.dsp.pipeline import analyse
from dranalyser.rules.engine import Rule, apply_rules, load_rules
from dranalyser.rules.features import incident_features
from dranalyser.synth.generator import SynthSpec, generate


def _rules(*ids):
    return [rule for rule in load_rules() if rule.id in ids]


def test_recorded_zone_two_trip_and_location_cannot_invent_zone_one_reach():
    case = generate(SynthSpec(m=.42))
    analyses = {end: analyse(record) for end, record in case.records.items()}
    for analysis in analyses.values():
        analysis.record.digital['TRIP Z2'] = np.array(analysis.record.digital['TRIP'], copy=True)
    features = incident_features(analyses, settings={})
    features.update(location_available=True, m=.42, km_from_S=42.)
    assert features['S_zone_operated'] == 'Z2'
    assert features['S_zone_timer_source'] == 'Not supplied'
    result = apply_rules(features, _rules('FL-02'))
    assert not result.findings
    assert len(result.skipped) == 1
    assert 'actual' in result.skipped[0].reason.lower()


@pytest.mark.parametrize(('rule_id', 'features'), [
    ('FL-01', dict(location_available=True, m=.95, S_zone_operated='Z1_OR_AIDED', S_carrier_recv=False)),
    ('FL-03', dict(S_zone_expected='Z1', S_zone_operated='Z2', S_z_app_r_sec=1., S_z_app_x_sec=2.)),
])
def test_zone_compliance_is_not_assessed_without_applicable_settings_and_loop_support(rule_id, features):
    result = apply_rules(features, _rules(rule_id))
    assert not result.findings
    assert result.skipped and result.skipped[0].rule_id == rule_id
    assert 'settings' in result.skipped[0].reason.lower()
    assert 'review' in result.skipped[0].reason.lower()


@pytest.mark.parametrize(('rule_id', 'features'), [
    ('CB-01', dict(S_breaker_ms=75., R_breaker_ms=None, S_trip_ms=20., S_open_ms=95.)),
    ('CB-04', dict(slowest_clear_ms=600., S_clear_ms=600., R_clear_ms=None)),
    ('AR-02', dict(S_dead_time_ms=1300., S_open_ms=100., S_ar_close_ms=1400.)),
])
def test_generic_timing_thresholds_remain_project_screens(rule_id, features):
    result = apply_rules(features, _rules(rule_id))
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert 'project' in finding.title.lower() or 'project' in finding.message.lower()
    assert 'not' in finding.message.lower()
    assert 'setting' in finding.message.lower() or 'specification' in finding.message.lower()
    assert result.verdict not in ('Correct operation', 'Correct but investigate', 'Incorrect operation')


def test_unavailable_or_empty_rule_evidence_cannot_claim_correct_operation():
    result = apply_rules({}, [Rule('X', 'Unavailable observation', 'critical', 'True', requires=['feedback'])])
    assert result.skipped and not result.findings
    assert result.verdict == 'No adverse finding in available evidence'
    assert apply_rules({}, []).verdict == 'No adverse finding in available evidence'


def test_unavailable_rule_preserves_reason_without_evaluating_unsupported_condition():
    rule = Rule('X', 'Zone assessment', 'critical', 'unsupported_feature > 0',
                unavailable_reason='Applicable settings and reviewed fault-loop support are unavailable.')
    result = apply_rules({}, [rule])
    assert not result.findings and not result.errors
    assert len(result.skipped) == 1 and rule.unavailable_reason in result.skipped[0].reason


def test_newly_rendered_report_versions_findings_and_preserves_distance():
    from tests.test_report import _synth_report
    report = _synth_report()
    assert 'data-rule-assessment-version="2"' in report.html
    assert 'Protection compliance is not assessed' in report.html
    assert 'Correct operation' not in report.html and 'Incorrect operation' not in report.html
    assert report.location.ok and report.location.method == 'E5'


@pytest.mark.parametrize(('rule_id', 'features'), [
    ('AR-03', dict(S_ar_lockout=True, R_ar_lockout=False, S_definitive_trip=False, R_definitive_trip=False)),
    ('AR-04', dict(S_definitive_trip=True, R_definitive_trip=False, S_ar_in_progress=True, R_ar_in_progress=False)),
    ('BU-04', dict(S_backup_picked_up=True, S_backup_operated=False)),
])
def test_command_and_pickup_indications_do_not_prove_physical_outcomes_or_compliance(rule_id, features):
    result = apply_rules(features, _rules(rule_id))
    assert len(result.findings) == 1 and not result.errors
    message = result.findings[0].message.lower()
    assert 'indication' in message and 'does not establish' in message
    assert 'grading' in message or 'physical' in message


@pytest.mark.parametrize(('fault', 'compensation'), [('AG', True), ('BG', True), ('AB', True), ('AG', False)])
def test_legacy_expected_zone_is_withheld_for_unreviewed_fault_loop_and_settings(fault, compensation):
    from dranalyser.registry.settings import PolygonChar, ProtectionSettings, Zone
    from dranalyser.rules.features import terminal_features
    analysis = analyse(generate(SynthSpec(fault=fault)).records['S'])
    # A generous declaration makes the old VA-only projection look eligible even
    # for BG/phase faults or an absent ground compensation. It is not a review.
    characteristic = PolygonChar(vertices=[(-1e6, -1e6), (1e6, -1e6), (1e6, 1e6), (-1e6, 1e6)])
    settings = ProtectionSettings(zones=[Zone('Z1', phase=characteristic, earth=characteristic)])
    if compensation:
        settings.k0_convention = 'impedances'
        settings.k0_params = dict(r1=1., x1=10., r0=3., x0=30.)
    assert analysis.indices().size and analysis.fault_type == fault
    values = terminal_features(analysis, 'S', settings).values
    assert values['zone_expected'] is None
    assert values['z_app_r_sec'] is None and values['z_app_x_sec'] is None
    assert 'not assessed' in values['zone_expected_reason'].lower()
    assert 'fault-loop' in values['zone_expected_reason'].lower()
    assert 'settings' in values['zone_expected_reason'].lower()


def test_cli_rule_findings_explain_withheld_zone_assessment(tmp_path, capsys):
    from types import SimpleNamespace
    from dranalyser.cli.commands import cmd_verdict
    from scripts.create_demo import create_demo
    source = create_demo(tmp_path / 'synthetic')
    assert cmd_verdict(SimpleNamespace(S=str(source / 'S/event.cfg'), R=None,
                                     line=str(source / 'synthetic-line.yaml'), rio=None, rules=None)) == 0
    output = capsys.readouterr().out
    assert 'S zone assessment: Not assessed' in output
    assert 'applicable settings' in output and 'fault-loop/compensation' in output
    assert 'Correct operation' not in output and 'Incorrect operation' not in output
