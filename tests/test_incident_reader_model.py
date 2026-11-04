"""Independent sample evidence and stored-location boundaries for reader reports."""
import copy
import hashlib
import json
import io
import shutil
from pathlib import Path

import pytest

from dranalyser.workbench import event_study
from dranalyser.workbench.incident_report import build_incident_report, _analogue_observations, _signal_label
from tests.test_event_study import source
from dranalyser.application.intake import Intake
from dranalyser.application.store import Store
from scripts.create_demo import create_demo
from dranalyser.application.worker import Worker


@pytest.fixture
def analysed_demo(tmp_path):
    source_folder = create_demo(tmp_path / 'synthetic')
    registry = tmp_path / 'registry'
    registry.mkdir()
    shutil.copyfile(source_folder / 'synthetic-line.yaml', registry / 'line.yaml')
    store = Store(tmp_path / 'app')
    streams = [(end + '/event.' + extension, io.BytesIO((source_folder / end / ('event.' + extension)).read_bytes()))
               for end in ('S', 'R') for extension in ('cfg', 'dat')]
    job, _ = Intake(store).ingest(streams, metadata=json.loads((source_folder / 'intake.json').read_text()))
    assert Worker(store, registry).once()
    row = store.get(job['incident_id'])
    assert row['state'] == 'completed'
    return store, row


def revision(names=('one.cfg', 'two.cfg')):
    return dict(incident_id='incident', number=1, files=[], metadata={},
        bundle=dict(files=[dict(name=name, kind='comtrade') for name in names]))


def saved_inputs(captures, regions=None, mappings=None, asserted_states=None):
    regions = regions or dict(pre=[0, 80], fault=[100, 220], post=None)
    return dict(version=1, inputs=dict(ends={name: dict(record=record, timing_mode='manual',
        mappings=mappings or {}, asserted_states=asserted_states or {}, **regions)
        for name, record in zip(('S', 'R'), captures, strict=False)}),
        bindings={name: value['source_sha256'] for name, value in zip(('S', 'R'), captures.values(), strict=False)})


@pytest.fixture
def captures(monkeypatch):
    values = {'one.cfg': source(), 'two.cfg': source('Remote', 'different-relay')}
    monkeypatch.setattr(event_study, '_source', lambda root, row, name: (values[name], {}))
    return values


def test_sample_values_use_complete_region_rms_independently_and_keep_zeros(captures):
    # Deliberately use same station/relay identity: these are display recordings,
    # so no false opposite-end assignment or same-event confirmation is needed.
    captures['two.cfg']['station'] = captures['one.cfg']['station']
    captures['two.cfg']['device'] = captures['one.cfg']['device']
    captures['one.cfg']['channels'][0]['values'] = [0.] * 240
    captures['one.cfg']['channels'][3]['values'] = [None] * 240
    original = copy.deepcopy(captures)
    report = build_incident_report('.', revision(), event_inputs=saved_inputs(captures))
    assert [row['display_label'] for row in report['sources']] == ['one', 'two']
    one, two = [{row['meaning']: row for row in item['phase_values']} for item in report['sources']]
    assert one['VA']['pre_rms'] == one['VA']['fault_rms'] == 0
    assert one['IA']['fault_rms'] is None
    assert 'complete known one-cycle' in one['IA']['missing_reasons']['fault']
    assert two['IA']['pre_rms'] == pytest.approx(1)
    assert two['IA']['fault_rms'] == pytest.approx(5)
    assert two['VA']['fault_rms'] == pytest.approx(50)
    assert two['IA']['post_rms'] is None and two['IA']['missing_reasons']['post']
    assert report['location']['km_from_S'] is None
    assert captures == original
    json.dumps(report, allow_nan=False)


def test_true_sample_rms_includes_dc_and_is_not_peak_divided_by_sqrt_two(captures):
    capture = captures['one.cfg']
    capture['channels'][3]['values'] = [3. if i < 100 else 4. for i in range(240)]
    # A 4 A constant has RMS 4 A, not peak/sqrt(2).
    report = build_incident_report('.', revision(), records=['one.cfg'], event_inputs=saved_inputs(captures))
    phase = next(row for row in report['sources'][0]['phase_values'] if row['meaning'] == 'IA')
    assert phase['pre_rms'] == pytest.approx(3)
    assert phase['fault_rms'] == pytest.approx(4)
    assert 'Median of complete trailing one-cycle' in phase['rms_basis']


def test_plain_findings_show_largest_supported_change_with_values_and_units(captures):
    captures['one.cfg']['channels'][3]['values'] = [1. if i < 100 else 8. for i in range(240)]
    report = build_incident_report('.', revision(), records=['one.cfg'], event_inputs=saved_inputs(captures))
    finding = next(text for text in report['findings'] if 'Before → during RMS' in text)
    assert 'R-phase current 1 → 8 A' in finding
    assert 'R-phase voltage 100 → 50 V' in finding
    assert len(finding) < 160
    assert finding.endswith('.') and 'increased' not in finding


def test_plain_observations_keep_real_zero_and_never_rank_counts_against_amperes():
    def row(meaning, phase, unit, before, during):
        return dict(meaning=meaning, phase=phase, units=unit, pre_rms=before, fault_rms=during)
    source = dict(phase_values=[row('IA', 'R', 'raw counts', 1000, 100000),
        row('IB', 'Y', 'A (CFG-declared, unverified)', 0, 2), row('IC', 'B', 'kA', .001, .0015),
        row('VA', 'R', 'raw counts', 0, 0), row('VB', 'Y', 'raw counts', 100, 50)])
    assert _analogue_observations(source) == [
        'Y-phase current 0 → 2 A', 'Y-phase voltage channel 100 → 50 raw counts']
    source['phase_values'][2]['fault_rms'] = .004
    assert _analogue_observations(source)[0] == 'B-phase current 1 → 4 A'
    source['phase_values'][1].update(pre_rms=1000, fault_rms=3000)
    source['phase_values'][3].update(units='V', pre_rms=127000, fault_rms=63000)
    assert _analogue_observations(source) == [
        'Y-phase current 1 → 3 kA', 'R-phase voltage 127 → 63 kV']


def test_unavailable_event_support_never_becomes_whole_record_fault_maximum(captures):
    for capture in captures.values():
        for channel in capture['channels']:
            channel['values'] = [10000.] * 240
    report = build_incident_report('.', revision())
    for record in report['sources']:
        assert record['fault'] is None
        assert all(row['fault_rms'] is None for row in record['phase_values'])
        assert all(row['missing_reasons']['pre'] for row in record['phase_values'])
        assert record['groups']['current'][0]['trace']


def test_saved_manual_regions_are_withheld_on_any_source_hash_change(captures):
    saved = saved_inputs(captures)
    saved['bindings']['S'] = {'event.cfg': 'other', 'event.dat': 'other'}
    report = build_incident_report('.', revision(), event_inputs=saved)
    first, second = report['sources']
    assert first['timing_mode'] == 'auto'
    assert 'source hashes differ' in first['observation_inputs_note']
    assert second['timing_mode'] == 'manual'
    assert second['fault'] == [100, 220]


def test_raw_counts_mapping_conflicts_and_missing_phases_have_named_unknowns(captures):
    capture = captures['one.cfg']
    capture['channels'][3]['units'] = 'raw counts'
    capture['channels'][0]['units'] = 'A (CFG-declared, unverified)'
    capture['channels'][1]['label'] = 'unknown vendor channel'
    report = build_incident_report('.', revision(), records=['one.cfg'], event_inputs=saved_inputs(captures, mappings={'A1': 'VA'}))
    record = report['sources'][0]
    rows = {row['meaning']: row for row in record['phase_values']}
    assert rows['IA']['units'] == 'raw counts'
    assert rows['IA']['fault_rms'] == pytest.approx(5)
    assert rows['VA']['fault_rms'] is None and 'mapping conflicts' in rows['VA']['missing_reasons']['fault']
    assert rows['VB']['fault_rms'] is None and 'No unique mapped' in rows['VB']['missing_reasons']['fault']
    assert not any(c['meaning'] == 'VA' for c in record['groups']['voltage'])
    assert len(record['phase_values']) == 6


def test_short_gapped_and_ongoing_regions_keep_missing_support(captures):
    capture = captures['one.cfg']
    capture['channels'][3]['values'][105:220] = [None] * 115
    capture['break_indices'] = [130]
    selected = saved_inputs(captures, dict(pre=[0, 15], fault=[100, 220], post=None))
    report = build_incident_report('.', revision(), records=['one.cfg'], event_inputs=selected)
    record = report['sources'][0]
    current = next(row for row in record['phase_values'] if row['meaning'] == 'IA')
    assert current['pre_rms'] is current['fault_rms'] is current['post_rms'] is None
    assert all(current['missing_reasons'].values())
    assert record['gaps']['break_indices'] == [130]
    assert record['gaps']['unknown_analog_samples'] == 115
    trace = next(row for row in record['groups']['voltage'] if row['meaning'] == 'VA')['trace']
    assert [130, .13, None] in trace
    assert any(point[2] is None for point in record['groups']['current'][0]['trace'])


def test_polarity_review_changes_observations_without_claiming_breaker_movement(captures):
    selected = saved_inputs(captures, mappings={'D1': 'TRIP'}, asserted_states={'D1': 0})
    report = build_incident_report('.', revision(), records=['one.cfg'], event_inputs=selected)
    event = report['sources'][0]['digital']['events'][0]
    assert event['kind'] == 'cleared' and event['asserted_state'] == 0
    assert event['plain_label'] == 'Trip command indication'
    assert event['source_bracket_s'] == [.129, .13]
    assert 'Recorded cleared indication' in event['observation']
    assert any('Commands do not prove breaker' in text for text in report['sources'][0]['digital']['insights'])
    text = json.dumps(report)
    assert 'poles opened' not in text and 'cross-country' not in text
    assert 'accuracy%' not in text and '/confirm' not in text


def test_plain_signal_labels_use_real_canonical_zone_and_receive_meanings():
    assert _signal_label('CARRIER_RECV', 'DIST. Chan Recv') == 'Protection message received indication'
    for zone in range(1, 5):
        assert _signal_label('Z'+str(zone), 'vendor zone') == 'Protection zone '+str(zone)+' indication'
    assert _signal_label('TRIP_Z2', 'vendor trip') == 'Protection zone 2 trip indication'


def test_used_primary_precedes_attachments_and_keeps_single_end_single(captures):
    row = revision()
    row['result'] = dict(used={'R': 'two.cfg'})
    report = build_incident_report('.', row, event_inputs=saved_inputs(captures))
    assert [item['record'] for item in report['sources']] == ['two.cfg']
    assert report['sources'][0]['display_label'] == 'two'
    assert report['attachments'][0]['status'] == 'attached; not plotted'


def test_source_without_timing_does_not_hide_other_source(captures):
    captures['one.cfg']['axis']['elapsed_s'] = []
    report = build_incident_report('.', revision(), records=['one.cfg', 'two.cfg'], event_inputs=saved_inputs(captures))
    assert report['sources'][0]['status'] == 'unavailable' and report['sources'][0]['reason']
    assert report['sources'][1]['status'] == 'available'
    assert next(row for row in report['sources'][1]['phase_values'] if row['meaning'] == 'IA')['fault_rms'] == pytest.approx(5)


def test_stored_native_fault_window_measurements_keep_distinct_rms_basis(captures):
    row = revision()
    row['result'] = dict(relay_evidence=[dict(file='one.cfg', status='analysed', measurements=dict(
        window=dict(start_s=.1, end_s=.22, sample_count=120), channels=[dict(channel='IA', rms=4.75, unit='A primary')]))])
    report = build_incident_report('.', row, records=['one.cfg'], event_inputs=saved_inputs(captures))
    record = report['sources'][0]
    assert record['operational_measurements']['channels'][0]['rms'] == 4.75
    assert 'sample-weighted RMS' in record['operational_measurements']['basis']
    assert next(row for row in record['phase_values'] if row['meaning'] == 'IA')['fault_rms'] == pytest.approx(5)


def test_reviewed_copy_is_preferred_and_does_not_become_second_capture(tmp_path, captures):
    folder = tmp_path / 'runs' / 'incident' / '1' / 'records'
    folder.mkdir(parents=True)
    reviewed = 'reviewed-ratios-123/reviewed.cfg'
    captures[reviewed] = copy.deepcopy(captures['one.cfg'])
    row = revision(('one.cfg', reviewed, 'two.cfg'))
    row['bundle']['root'] = str(folder)
    row['bundle']['files'][0]['data_file'] = 'one.dat'
    row['files'] = [dict(name='one.cfg', sha256='source-cfg'), dict(name='one.dat', sha256='source-dat')]
    manifest = dict(original_file='one.cfg', original_sha256={'one.cfg': 'source-cfg', 'one.dat': 'source-dat'},
        samples_changed=False, clock_changed=False, original_files_unchanged=True)
    raw = json.dumps(manifest).encode()
    path = folder / 'reviewed-ratios-123' / 'instrument-review.json'
    path.parent.mkdir()
    path.write_bytes(raw)
    row['files'].append(dict(name='reviewed-ratios-123/instrument-review.json', sha256=hashlib.sha256(raw).hexdigest()))
    report = build_incident_report(tmp_path, row)
    assert [item['record'] for item in report['sources']] == [reviewed, 'two.cfg']
    assert report['attachments'][0]['status'] == 'same-capture attachment'
    assert len(report['sources']) == 2
    explicit = build_incident_report(tmp_path, row, records=['one.cfg', reviewed])
    assert [item['record'] for item in explicit['sources']] == ['one.cfg']
    assert explicit['attachments'][1]['status'] == 'same-capture attachment'
    assert 'not counted twice' in explicit['attachments'][1]['reason']
    reversed_order = build_incident_report(tmp_path, row, records=[reviewed, 'one.cfg'])
    assert [item['record'] for item in reversed_order['sources']] == [reviewed]


def test_known_42km_existing_engine_value_and_source_revision_model_gates(analysed_demo):
    store, row = analysed_demo
    original = copy.deepcopy(row)
    model = build_incident_report(store.root, row)
    assert model['location']['km_from_S'] == pytest.approx(41.98828243177587, abs=1e-10)
    assert model['location']['method'] == 'E5'
    assert model['location']['reference_label'] == 'Synthetic S'
    assert row == original
    assert build_incident_report(store.root, row, records=['R/event.cfg'])['location']['km_from_S'] is None
    for key, bad in [('binding', {}), ('source_records', {'S': 'other.cfg'}), ('input_sha256', 'stale')]:
        altered = copy.deepcopy(row)
        altered['result']['location_summary'][key] = bad
        assert build_incident_report(store.root, altered)['location']['km_from_S'] is None
    legacy = copy.deepcopy(row)
    legacy['result'].pop('location_summary')
    assert build_incident_report(store.root, legacy)['location']['km_from_S'] is None
    provisional = copy.deepcopy(row)
    provisional['result']['parameter_status'] = 'provisional'
    assert build_incident_report(store.root, provisional)['location']['km_from_S'] is None
    # Reports do not introduce another numerical answer or mutate old evidence.
    assert row == original
    assert Path(row['result']['line_snapshot']).is_file()


def test_valid_mapped_equivalent_and_changed_phase_location_gates(analysed_demo):
    store, row = analysed_demo
    saved = dict(version=1, inputs=dict(ends={}), bindings={})
    for end in ('S', 'R'):
        capture, _ = event_study._source(store.root, row, end + '/event.cfg')
        saved['inputs']['ends'][end] = dict(record=end + '/event.cfg', timing_mode='auto', mappings={'A1': capture['channels'][0]['label']})
        saved['bindings'][end] = capture['source_sha256']
    model = build_incident_report(store.root, row, event_inputs=saved)
    assert model['location']['method'] == 'E5'
    saved['inputs']['ends']['S']['mappings'] = {'A1': 'VB'}
    assert build_incident_report(store.root, row, event_inputs=saved)['location']['km_from_S'] is None


def test_unknown_classification_and_source_saturation_are_plain_and_keep_estimate(analysed_demo):
    store, row = analysed_demo
    summary = row['result']['location_summary']
    expected = summary['km_from_S']
    summary['fault_type'] = 'NONE'
    row['result']['relay_evidence'][0]['ct_saturation'] = True
    model = build_incident_report(store.root, row)
    assert model['location']['km_from_S'] == expected
    assert model['summary']['classification']['label'] == 'Not established'
    assert any('possible current-transformer saturation' in text for text in model['findings'])
    assert model['location']['caveats'] == summary['caveats']
    assert model['location']['diagnostic_interval_km'] == summary['interval_km']


def test_many_explicit_breaks_keep_trace_budget_and_unknown_digital_edge(captures):
    capture = captures['one.cfg']
    capture['break_indices'] = list(range(1, 240))
    model = build_incident_report('.', revision(), records=['one.cfg'], event_inputs=saved_inputs(captures))
    record = model['sources'][0]
    assert len(record['gaps']['break_indices']) == 128
    assert record['gaps']['omitted_break_indices'] == 111
    for group in record['groups'].values():
        for channel in group:
            assert len(channel['trace']) <= 800
            assert len(channel['rms_trace']) <= 800
    edge = record['digital']['events'][0]
    assert edge['kind'] == 'state difference across gap'
    assert not edge['interpretation_available']
    assert 'no transition time' in edge['observation']


def test_default_source_scan_stops_after_two_recoverable_captures(captures, monkeypatch):
    captures['one.cfg']['axis']['elapsed_s'] = []
    captures['three.cfg'] = source('Third', 'relay-3')
    captures['four.cfg'] = source('Fourth', 'relay-4')
    calls = []

    def decode(root, row, name):
        calls.append(name)
        return captures[name], {}

    monkeypatch.setattr(event_study, '_source', decode)
    model = build_incident_report('.', revision(('one.cfg', 'two.cfg', 'three.cfg', 'four.cfg')))
    assert [row['record'] for row in model['sources']] == ['two.cfg', 'three.cfg']
    assert 'four.cfg' not in calls
    assert len(model['attachments']) == 4


def test_selected_frozen_checksum_failure_is_never_replaced_by_missing_data(captures, monkeypatch):
    def changed(root, row, name):
        raise ValueError('Source checksum differs from the frozen revision.')

    monkeypatch.setattr(event_study, '_source', changed)
    with pytest.raises(ValueError, match='checksum'):
        build_incident_report('.', revision(), records=['one.cfg'])


def test_supporting_attachments_remain_visible_without_counting_dat_as_capture(captures):
    row = revision()
    row['bundle']['files'][0]['data_file'] = 'one.dat'
    row['files'] = [dict(name=name, sha256='hash-' + name) for name in ('one.cfg', 'one.dat', 'settings.rio', 'event.pdf')]
    model = build_incident_report('.', row, records=['one.cfg'])
    attachments = {entry['record']: entry for entry in model['attachments']}
    assert 'one.dat' not in attachments
    assert attachments['settings.rio']['status'] == 'supporting attachment; not plotted'
    assert attachments['event.pdf']['source_sha256'] == 'hash-event.pdf'
    assert len(model['sources']) == 1



def test_saved_observation_display_name_is_not_overwritten(captures):
    saved = saved_inputs(captures)
    saved['inputs']['ends']['S']['substation'] = 'Reviewed observation station'
    report = build_incident_report('.', revision(), event_inputs=saved)
    assert report['sources'][0]['display_label'] == 'Reviewed observation station'
    assert report['sources'][1]['display_label'] == 'two'
