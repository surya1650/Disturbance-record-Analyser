"""Per-relay identity/evidence survives intake, primary changes and revisions."""
import io
import json

import pytest

from dranalyser.application.intake import metadata_value
from dranalyser.application.worker import Worker
from tests import test_application as fixtures

environment = fixtures.environment
payload = fixtures.payload


def pair_payload(root, end, system, change=False):
    files = []
    for ext in ("cfg", "dat"):
        data = (root / end / f"event.{ext}").read_bytes()
        if change and ext == "cfg":
            # Distinct recorder header, identical physical waveform; no duplicate collapse.
            data = data.replace(b",", b"-second,", 1)
        files.append(('files', (f'{end}/{system}/event.{ext}', data, 'application/octet-stream')))
    return files


def test_four_relays_keep_identity_and_evidence_when_primary_changes(environment):
    client, app, source, registry = environment
    assignments, files = {}, []
    for end in ("S", "R"):
        for system in ("Main-1", "Main-2"):
            files.extend(pair_payload(source, end, system, change=system == "Main-2"))
            assignments[f'{end}/{system}/event.cfg'] = {
                "end": end, "role": "primary" if system == "Main-1" else "corroborating",
                "protection_system": system}
    row = client.post('/api/intake', files=files, data={"metadata": json.dumps({
        "assignments": assignments, "auto_analyse": True})}).json()
    identity = row['incident_id']
    worker = Worker(app.state.store, registry)
    assert worker.once()
    row = client.get(f'/api/incidents/{identity}').json()
    assert row['state'] == 'completed', row
    evidence = row['result']['relay_evidence']
    assert len(evidence) == 4
    assert {(r['end'], r['protection_system']) for r in evidence} == {
        (end, system) for end in ('S', 'R') for system in ('Main-1', 'Main-2')}
    assert all(r['status'] == 'analysed' for r in evidence)
    assert all(r['stages']['record_hash'] == r['record_hash'] for r in evidence)
    assert all(not r['clock_quality']['alignment_eligible'] for r in evidence)
    assert len(row['result']['standards_audits']) == 4
    assert not any(a.get('error') for a in row['result']['standards_audits'])
    comparisons = row['result']['operation_comparisons']
    assert len(comparisons) == 6
    assert sum(p['scope'] == 'same terminal' for p in comparisons) == 2
    assert all(p['association']['applied'] is False for p in comparisons)
    assert all(not p['stage_association']['confirmed'] for p in comparisons)
    assert [p['scope'] for p in comparisons[:2]] == ['same terminal', 'same terminal']
    first = client.get(f'/api/incidents/{identity}/report?revision=1').content
    assert b'All-relay evidence' in first and b'Main-2' in first
    assert b'Operation comparisons and onset association' in first
    assert b'Fault-stage observation intervals' in first and b'Clock-quality evidence' in first
    assert b'No fault location was produced' in first  # operational evidence needs no line constants
    assert client.post(f'/api/incidents/{identity}/reanalyse?revision=1').status_code == 202
    assert worker.once()
    for v in assignments.values():
        v['role'] = 'primary' if v['protection_system'] == 'Main-2' else 'corroborating'
    assert client.post(f'/api/incidents/{identity}/review', json={
        'revision': 2, 'assignments': assignments}).status_code == 202
    assert worker.once()
    second = client.get(f'/api/incidents/{identity}').json()['result']['relay_evidence']
    assert client.get(f'/api/incidents/{identity}').json()['result']['operation_comparisons'] == comparisons
    assert len(second) == 4
    by_file = {r['file']: r for r in evidence}
    for r in second:
        old = by_file[r['file']]
        assert r['signals'] == old['signals'] and r['measurements'] == old['measurements']
        assert r['stages'] == old['stages'] and r['clock_quality'] == old['clock_quality']
        assert r['protection_system'] == old['protection_system'] and r['role'] != old['role']
    assert client.get(f'/api/incidents/{identity}/report?revision=1').content == first


def test_missing_remote_and_corrupt_record_stay_visible(environment):
    client, app, source, registry = environment
    files = payload(source) + [('files', ('bad.cfg', io.BytesIO(b'bad cfg'), 'application/octet-stream'))]
    response = client.post('/api/intake', files=files, data={"metadata": json.dumps({
        "auto_analyse": True, "assignments": {"S/event.cfg": {"end": "S", "role": "primary"}}})})
    worker = Worker(app.state.store, registry)
    assert worker.once()
    row = client.get(f"/api/incidents/{response.json()['incident_id']}").json()
    records = row['result']['relay_evidence']
    assert any(r['file'] == 'bad.cfg' and r['status'] == 'unavailable' for r in records)
    assert row['result']['terminal_evidence'][1]['summary'] == 'record unavailable; operation unknown'


def test_stage_review_persists_and_identity_change_invalidates_it_without_rewriting_history(environment):
    client, app, source, registry = environment
    files = pair_payload(source, 'S', 'Main-1') + pair_payload(source, 'S', 'Main-2', change=True)
    assignments = {f'S/{system}/event.cfg': {'end': 'S', 'role': role, 'protection_system': system}
                   for system, role in [('Main-1', 'primary'), ('Main-2', 'corroborating')]}
    response = client.post('/api/intake', files=files, data={'metadata': json.dumps({
        'auto_analyse': True, 'assignments': assignments})})
    identity = response.json()['incident_id']
    worker = Worker(app.state.store, registry)
    assert worker.once()
    rows = client.get(f'/api/incidents/{identity}').json()['result']['relay_evidence']
    first = client.get(f'/api/incidents/{identity}/report?revision=1').content
    for r in rows:
        stages = r['stages']
        assert stages['status'] == 'observed' and not stages['quality_reasons'], stages
        stage = next(s for s in stages['intervals'] if s['stable'] and s['phase_pattern'])
        assignments[r['file']]['stage_review'] = {
            'inventory_hash': stages['inventory_hash'], 'reviewer': 'Synthetic QA <reviewer>',
            'reason': 'Same generated waveform with distinct synthetic recorder headers',
            'groups': {stage['id']: 'initial'}, 'same_incident': True, 'same_circuit': True, 'stage_identity': True}
    for old_revision in (1, 2):
        assert client.post(f'/api/incidents/{identity}/reanalyse?revision={old_revision}').status_code == 202
        assert worker.once()
        if old_revision == 2:
            assignments['S/Main-2/event.cfg']['protection_system'] = 'other'
        assert client.post(f'/api/incidents/{identity}/review', json={
            'revision': old_revision+1, 'assignments': assignments}).status_code == 202
        assert worker.once()
        result = client.get(f'/api/incidents/{identity}').json()['result']
        pair = result['operation_comparisons'][0]['stage_association']
        assert pair['confirmed'] == (old_revision == 1)
        assert not pair['applied']
        if old_revision == 1:
            second = client.get(f'/api/incidents/{identity}/report?revision=2').content
            assert b'Synthetic QA &lt;reviewer&gt;' in second
            nav = client.get(f'/api/incidents/{identity}/navigator?revision=2').json()
            assert all(n['stages']['review_status'] == 'valid reviewer declaration' for n in nav['records'])
        else:
            changed = next(r for r in result['relay_evidence'] if r['protection_system'] == 'other')
            assert changed['stages']['review_status'].startswith('stale')
            assert client.get(f'/api/incidents/{identity}/report?revision=2').content == second
    assert client.get(f'/api/incidents/{identity}/report?revision=1').content == first


def test_protection_system_is_optional_and_not_inferred_from_primary():
    out = metadata_value({'assignments': {'a.cfg': {'end': 'S', 'role': 'primary'}}})
    assert 'protection_system' not in out['assignments']['a.cfg']
    with pytest.raises(ValueError, match='protection system'):
        metadata_value({'assignments': {'a.cfg': {'end': 'S', 'role': 'primary', 'protection_system': 'GPS'}}})


def test_different_relay_observations_are_warned_above_selected_record_verdict(environment):
    client, app, source, registry = environment
    files = pair_payload(source, 'S', 'Main-1') + pair_payload(source, 'S', 'Main-2', change=True)
    cfg = (source/'S/event.cfg').read_text().splitlines()
    na, nd = (int(s[:-1]) for s in cfg[1].split(',')[1:])
    trip = next(i for i, s in enumerate(cfg[2+na:2+na+nd]) if s.split(',')[1] == 'TRIP')
    fields = [s.split(',') for s in files[-1][1][1].decode().splitlines()]
    for row in fields:
        row[2+na+trip] = '0'
    files[-1] = ('files', (files[-1][1][0], ('\n'.join(','.join(r) for r in fields)+'\n').encode()))
    response = client.post('/api/intake', files=files, data={'metadata': json.dumps({
        'auto_analyse': True, 'assignments': {
            'S/Main-1/event.cfg': {'end': 'S', 'role': 'primary', 'protection_system': 'Main-1'},
            'S/Main-2/event.cfg': {'end': 'S', 'role': 'corroborating', 'protection_system': 'Main-2'}}})})
    assert Worker(app.state.store, registry).once()
    identity = response.json()['incident_id']
    result = client.get(f'/api/incidents/{identity}').json()['result']
    assert result['operation_comparisons'][0]['status'] == 'review differences'
    html = client.get(f'/api/incidents/{identity}/report').text
    assert html.index('Review relay differences') < html.index('Selected-record rule assessment')


def test_corroborating_analysis_failure_keeps_actual_reason(environment, monkeypatch):
    from dranalyser.workbench import incident

    client, app, source, registry = environment
    original = incident.analyse

    def fail_second(rec, **kwargs):
        if '-second' in rec.station:
            raise RuntimeError('synthetic analysis failure')
        return original(rec, **kwargs)

    monkeypatch.setattr(incident, 'analyse', fail_second)
    files = pair_payload(source, 'S', 'Main-1') + pair_payload(source, 'S', 'Main-2', change=True)
    response = client.post('/api/intake', files=files, data={'metadata': json.dumps({
        'auto_analyse': True, 'assignments': {
            'S/Main-1/event.cfg': {'end': 'S', 'role': 'primary'},
            'S/Main-2/event.cfg': {'end': 'S', 'role': 'corroborating'}}})})
    assert Worker(app.state.store, registry).once()
    row = client.get(f"/api/incidents/{response.json()['incident_id']}").json()
    record = next(r for r in row['result']['relay_evidence'] if r['file'] == 'S/Main-2/event.cfg')
    assert record['status'] == 'unavailable'
    assert 'RuntimeError synthetic analysis failure' in record['reason']
    assert row['result']['terminal_evidence'][0]['analysed'] == 1
