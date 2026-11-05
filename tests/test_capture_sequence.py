"""Separate captures form a bounded declared chronology, never joined samples."""
import copy
import json

import pytest

from dranalyser.comtrade.source_time import source_time_axis
from dranalyser.report.incident_summary import render_incident_report
from dranalyser.workbench.capture_sequence import capture_time, build_capture_sequence, signal_inventory
from dranalyser.workbench.incident_report import build_incident_report
from dranalyser.workbench import event_study
from tests.test_event_study import source as sample_source
from tests.test_incident_reader_model import revision, saved_inputs


def capture(record='one.cfg', start='05/11/2026,12:00:00', *, offsets=(0, 1)):
    raw = dict(recorded_times=dict(start=start), sample_count=3,
        axis=source_time_axis([1, 2, 3], [offsets[0]*1e6, (offsets[0]+offsets[1])/2*1e6, offsets[1]*1e6], nrates=0, timemult=1))
    return dict(record=record, station='Station', device='Relay', display_label=record,
        capture_time=capture_time(raw), digital=dict(sequence_signals=dict(missing=['Trip', 'AR', 'CB position feedback'])))


def test_declared_gap_sorts_reversed_selection_without_touching_sources_or_clocks():
    first, second = capture(), capture('two.cfg', '05/11/2026,12:00:03')
    sources = [second, first]
    original = copy.deepcopy(sources)
    sequence = build_capture_sequence(sources)
    assert [row['record'] for row in sequence['captures']] == ['one.cfg', 'two.cfg']
    assert sequence['relation'] == dict(status='gap', seconds=2, signed_seconds=2)
    assert sequence['status'] == 'candidate same-recorder sequence'
    assert sequence['chronology'] == 'declared local capture start order'
    assert 'identity unverified' in sequence['note'] and 'States between captures are unknown' in sequence['note']
    assert 'trip–reclose–retrip is unconfirmed' in sequence['note']
    assert not sequence['alignment_eligible'] and not sequence['clock_accuracy_verified']
    assert not sequence['authorizes_location']
    assert sources == original
    assert 'samples' not in sequence and 'waveform' not in sequence
    json.dumps(sequence, allow_nan=False)


def test_actual_nonzero_dat_origin_controls_order_span_and_overlap():
    # A later CFG start can still contain earlier actual samples.
    first = capture(offsets=(5, 7))
    second = capture('two.cfg', '05/11/2026,12:00:03', offsets=(1, 2))
    sequence = build_capture_sequence([first, second])
    assert sequence['captures'][0]['record'] == 'two.cfg'
    assert sequence['captures'][0]['first_local_iso'] == '2026-11-05T12:00:04'
    assert sequence['relation']['status'] == 'touching declared endpoints'
    second = capture('two.cfg', '05/11/2026,12:00:06')
    sequence = build_capture_sequence([first, second])
    assert sequence['relation']['status'] == 'overlap' and sequence['relation']['seconds'] == 1


def test_nanosecond_cfg_precision_and_midnight_are_preserved():
    sequence = build_capture_sequence([capture(start='05/11/2026,23:59:59.123456789'),
        capture('two.cfg', '06/11/2026,00:00:01.123456790')])
    assert sequence['captures'][0]['last_local_iso'] == '2026-11-06T00:00:00.123456789'
    assert sequence['relation']['seconds'] == pytest.approx(1.000000001)
    assert '1.000000001 s gap' in sequence['note']


@pytest.mark.parametrize('change', ['missing_station', 'missing_device', 'different', 'one_only'])
def test_missing_or_different_identity_never_becomes_same_recorder(change):
    sources = [capture(), capture('two.cfg')]
    if change == 'missing_station':
        sources[0]['station'] = ' '
    elif change == 'missing_device':
        sources[1]['device'] = ''
    elif change == 'different':
        sources[1]['device'] = 'Other relay'
    else:
        sources.pop()
    sequence = build_capture_sequence(sources)
    assert sequence['status'] != 'candidate same-recorder sequence'
    assert sequence['relation']['status'] == 'unknown' and not sequence['note']


@pytest.mark.parametrize('basis', [None, 'Explicit single CFG sample rate; DAT timestamps are noncritical.'])
def test_elapsed_zero_and_rate_generated_axis_do_not_prove_dat_origin(basis):
    raw = dict(recorded_times=dict(start='05/11/2026,12:00:00'), sample_count=3,
        axis=source_time_axis([1, 2, 3], [0, 500000, 1000000], nrates=0, timemult=1))
    if basis is None:
        raw['axis'].pop('declared_origin')
    else:
        raw['axis']['basis'] = basis
    one = capture()
    one['capture_time'] = capture_time(raw)
    sequence = build_capture_sequence([one, capture('two.cfg', '05/11/2026,12:00:03')])
    assert sequence['relation']['status'] == 'unknown'
    assert sequence['captures'][0]['first_local_iso'] is None
    assert 'gap/overlap unknown' in sequence['note']


def test_unparseable_start_never_uses_trigger_or_report_generation_time():
    one = capture(start='bad')
    sequence = build_capture_sequence([one, capture('two.cfg')])
    assert sequence['chronology'] == 'unknown' and sequence['relation']['status'] == 'unknown'
    assert one['capture_time']['cfg_start_local_iso'] is None


def test_inventory_names_absent_trip_ar_feedback_and_reuses_assignments():
    source = dict(digital=[dict(key='D1', label='Zone 1'), dict(key='D2', label='unknown')])
    inventory = signal_inventory(source, {})
    assert inventory['missing'] == ['Trip', 'AR', 'CB position feedback']
    assert 'No assigned Trip, AR, CB position feedback channels.' == inventory['missing_note']
    assert 'Z1' in inventory['channels'][0]['meanings']
    assert signal_inventory(source, {'D2': 'AR_CLOSE'})['missing'] == ['Trip', 'CB position feedback']
    assert signal_inventory(source, {'D1': 'ignore'})['channels'][0]['meanings'] == []
    assert signal_inventory(source, {'D2': 'EF_TRIP'})['missing'] == ['AR', 'CB position feedback']


def test_sequence_is_bounded_and_source_bound_stages_are_only_reused():
    sources = [capture(), capture('two.cfg'), capture('third.cfg')]
    stages = dict(status='observed', record_hash='hash', method='Existing stage screen',
        intervals=[dict(id='stage-'+str(i), kind='renewed current candidate', start_s=i, end_s=i+1) for i in range(20)])
    revision = dict(bundle=dict(files=[dict(name='one.cfg', content_hash='hash')]),
        result=dict(relay_evidence=[dict(file='one.cfg', record_hash='hash', status='analysed', stages=stages)]))
    sequence = build_capture_sequence(sources, revision, [True, True, True])
    assert len(sequence['captures']) == 2 and sequence['omitted_captures'] == 1
    stored = sequence['captures'][0]['stages']
    assert stored['method'] == 'Existing stage screen' and len(stored['intervals']) == 16
    assert stored['omitted_intervals'] == 4
    assert build_capture_sequence(sources, revision, [False, True])['captures'][0]['stages']['intervals'] == []
    revision['result']['relay_evidence'][0]['record_hash'] = 'stale'
    assert build_capture_sequence(sources, revision, [True, True])['captures'][0]['stages']['intervals'] == []


def test_report_escapes_sequence_text_and_keeps_four_independent_pages():
    hostile = '<img src=x onerror=alert(1)>'
    sources = [capture(hostile+'.cfg'), capture('two.cfg', '05/11/2026,12:00:03')]
    for source in sources:
        source.update(groups={}, phase_values=[])
    model = dict(sources=sources, incident_id='synthetic', revision=1, capture_sequence=build_capture_sequence(sources))
    model['capture_sequence']['note'] += hostile
    original = copy.deepcopy(model)
    html = render_incident_report(model)
    assert html.count('<section class="page"') == 4
    assert '2 s gap' in html and 'Sequence 1' in html and 'Sequence 2' in html
    assert '2026-11-05 12:00:00' in html and 'No assigned' not in html
    assert hostile not in html and '&lt;img src=x onerror=alert(1)&gt;' in html
    assert model == original


def test_single_native_primary_retains_same_recorder_capture_and_named_absence(monkeypatch):
    captures = {'one.cfg': sample_source(), 'two.cfg': sample_source()}
    for index, capture_source in enumerate(captures.values()):
        capture_source['recorded_times'] = dict(start='05/11/2026,12:00:0'+str(index+1))
        capture_source['axis'] = source_time_axis(list(range(240)), list(range(0, 240000, 1000)), nrates=0, timemult=1)
        capture_source['digital'] = [dict(key='D1', label='Zone 1', states=[0]*120+[1]*120)]
    monkeypatch.setattr(event_study, '_source', lambda root, row, name: (captures[name], {}))
    row = revision()
    row['result'] = dict(used={'S': 'one.cfg'})
    for item in row['bundle']['files']:
        item.update(station='Sending', device_id='relay-1')
    model = build_incident_report('.', row, event_inputs=saved_inputs(captures))
    assert [source['record'] for source in model['sources']] == ['one.cfg', 'two.cfg']
    assert model['capture_sequence']['relation']['seconds'] == pytest.approx(.761)
    html = render_incident_report(model)
    assert 'No assigned Trip, AR, CB position feedback channels.' in html
    assert model['location']['km_from_S'] is None and model['capture_sequence']['alignment_eligible'] is False
    explicit = build_incident_report('.', row, records=['one.cfg'], event_inputs=saved_inputs(captures))
    assert len(explicit['sources']) == 1
    # No opposite-end assignment, merged axis or observations in the gap is created.
    assert row['result']['used'] == {'S': 'one.cfg'}
    assert all(source['time_range_s'] == [0, .239] for source in model['sources'])


def test_report_primary_review_names_user_basis_without_cfg_or_ratio_claim(monkeypatch):
    capture_source = sample_source()
    capture_source['instrument_review'] = dict(basis='PRIMARY', confirmed_primary=True,
        primary_channels=['A4'], ratios={})
    monkeypatch.setattr(event_study, '_source', lambda *args: (capture_source, {}))
    model = build_incident_report('.', revision(('one.cfg',)), records=['one.cfg'])
    current = next(phase for phase in model['sources'][0]['phase_values'] if phase['id'] == 'A4')
    assert 'user-declared PRIMARY measurement basis' in current['scaling_note']
    assert 'CT/VT multiplication is not applied' in current['scaling_note']
    assert 'CFG-declared' not in current['scaling_note']


def test_default_peer_selection_requires_identity_and_skips_unavailable_or_duplicate(monkeypatch):
    from dranalyser.workbench.capture_sequence import same_recorder_attachments
    calls = []
    inventory = [dict(name=name, station='Station', device_id='Relay') for name in
        ('primary.cfg', 'duplicate.cfg', 'broken.cfg', 'peer.cfg', 'later.cfg')]
    inventory[1]['duplicate_of'] = 'primary.cfg'
    def load(root, revision, name):
        calls.append(name)
        return dict(axis=dict(elapsed_s=[] if name == 'broken.cfg' else [0, 1, 2])), {}
    monkeypatch.setattr(event_study, '_source', load)
    assert same_recorder_attachments('.', {}, ['primary.cfg'], inventory) == ['peer.cfg']
    assert calls == ['broken.cfg', 'peer.cfg']
    calls.clear()
    inventory[0]['device_id'] = ''
    assert same_recorder_attachments('.', {}, ['primary.cfg'], inventory) == [] and calls == []
    inventory[0]['device_id'] = 'Another relay'
    assert same_recorder_attachments('.', {}, ['primary.cfg'], inventory) == [] and calls == []
