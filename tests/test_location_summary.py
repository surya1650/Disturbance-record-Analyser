"""P2: persisted method-labelled location is exact, source-bound and JSON-safe."""
import copy
import json
import math

import pytest

from dranalyser.application.worker import Worker
from dranalyser.workbench.location_summary import digest, public
from dranalyser.workbench.source_snapshot import line_facts
from tests import test_application as fixtures
from tests.test_application import payload

environment = fixtures.environment


def test_public_diagnostics_omit_implementation_details_and_nonfinite_values():
    value = public({'_km_fn': lambda m: m, 'bad': math.inf, 'nested': {'_secret': 1, 'phase': complex(2, 3)},
                    'callback': lambda: 1, 'array': [1, math.nan]})
    assert value == {'bad': None, 'nested': {'phase': {'real': 2.0, 'imag': 3.0}}, 'array': [1, None]}
    json.dumps(value, allow_nan=False)
    assert digest({'b': 1, 'a': 2}) == digest({'a': 2, 'b': 1})
    assert digest({'_named_source.cfg': 1}) != digest({'_named_source.cfg': 2})


def test_synthetic_location_persists_engine_e5_with_exact_revision_sources(environment):
    client, app, source, registry = environment
    identity = client.post('/api/intake', files=payload(source) + payload(source, 'R'),
                           data={'metadata': (source / 'intake.json').read_text()}).json()['incident_id']
    assert Worker(app.state.store, registry).once()
    row = app.state.store.get(identity)
    assert row['state'] == 'completed', row['error']
    summary = row['result']['location_summary']
    assert summary['version'] == 1 and summary['status'] == 'accepted' and summary['accepted']
    assert summary['method'] == 'E5' and summary['mode'] == 'two-ended' and summary['fault_type'] == 'AG'
    assert summary['km_from_S'] == pytest.approx(41.988, abs=.001)
    assert summary['km_from_R'] == pytest.approx(100 - summary['km_from_S'])
    assert summary['reference'] == 'S'
    assert summary['binding']['files_sha256'] == {f['name']: f['sha256'] for f in row['files']}
    assert summary['source_records'] == {'S': 'S/event.cfg', 'R': 'R/event.cfg'}
    assert all(w['n_phasors'] > 0 and w['t_end'] > w['t_start'] for w in summary['supported_windows'].values())
    assert all(not e['accepted'] for e in summary['estimates'] if e['method'] == 'E4')
    assert '_km_fn' not in json.dumps(summary, allow_nan=False)
    facts = line_facts(app.state.store.root, row)
    assert facts['location']['method'] == 'E5' and facts['location']['overlay_eligible']
    assert facts['location']['km_from_S'] == summary['km_from_S']

    # New evidence cannot be replaced with a legacy prose number if binding fails.
    for kind in ('metadata', 'source', 'line', 'assignment', 'revision', 'schema'):
        changed = copy.deepcopy(row)
        s = changed['result']['location_summary']
        if kind == 'metadata':
            changed['metadata']['line_id'] = 'OTHER'
        elif kind == 'source':
            changed['files'][0]['sha256'] = '0' * 64
        elif kind == 'line':
            s['line']['sha256'] = '0' * 64
        elif kind == 'assignment':
            s['source_records'] = {'S': 'R/event.cfg'}
        elif kind == 'revision':
            s['binding']['revision'] += 1
        else:
            s['version'] = 99
        location = line_facts(app.state.store.root, changed)['location']
        assert location['km_from_S'] is None and not location['overlay_eligible'], kind


def test_single_end_then_late_remote_keeps_old_summary_and_report(environment):
    client, app, source, registry = environment
    identity = client.post('/api/intake', files=payload(source)).json()['incident_id']
    worker = Worker(app.state.store, registry)
    worker.once()
    response = client.post(f'/api/incidents/{identity}/review', json={'revision': 1,
        'line_id': 'SYNTHETIC-DEMO', 'assignments': {'S/event.cfg': {'end': 'S', 'role': 'primary'}}})
    assert response.status_code == 202
    worker.once()
    first = copy.deepcopy(app.state.store.get(identity))
    assert first['result']['location_summary']['mode'] == 'single-ended'
    report = client.get(f'/api/incidents/{identity}/report?revision=1').content
    response = client.post('/api/intake', files=payload(source, 'R'), data={'incident_id': identity,
        'expected_revision': '1', 'metadata': json.dumps({'auto_analyse': True,
            'assignments': {'R/event.cfg': {'end': 'R', 'role': 'primary'}}})})
    assert response.status_code == 202
    worker.once()
    second = app.state.store.get(identity)
    assert second['result']['location_summary']['mode'] == 'two-ended'
    assert second['result']['location_summary']['method'] == 'E5'
    assert app.state.store.get(identity, 1)['result']['location_summary'] == first['result']['location_summary']
    assert client.get(f'/api/incidents/{identity}/report?revision=1').content == report


def test_refused_model_summary_cannot_fall_back_to_legacy_distance(environment):
    client, app, source, registry = environment
    # A provisional review-required line is a supported, explicit abstention.
    path = registry / 'demo.yaml'
    path.write_text(path.read_text() + '\nmodel_review_required: true\n')
    identity = client.post('/api/intake', files=payload(source) + payload(source, 'R'),
        data={'metadata': (source / 'intake.json').read_text()}).json()['incident_id']
    Worker(app.state.store, registry).once()
    row = app.state.store.get(identity)
    summary = row['result']['location_summary']
    assert summary['status'] == 'refused' and not summary['accepted']
    assert summary['km_from_S'] is None and summary['caveats']
    row['result']['location_text'] = '42.000 km from Synthetic S by E5 (two-ended)'
    location = line_facts(app.state.store.root, row)['location']
    assert location['km_from_S'] is None and not location['overlay_eligible']


def test_source_only_report_has_explicit_uncomputed_summary(environment):
    client, app, source, registry = environment
    identity = client.post('/api/intake', files=payload(source)).json()['incident_id']
    worker = Worker(app.state.store, registry)
    worker.once()
    assert client.post(f'/api/incidents/{identity}/review', json={'revision': 1,
        'assignments': {'S/event.cfg': {'end': 'S', 'role': 'primary'}}}).status_code == 202
    worker.once()
    row = app.state.store.get(identity)
    assert row['result']['location_summary']['status'] == 'not_computed'
    assert row['result']['location_summary']['km_from_S'] is None
    assert line_facts(app.state.store.root, row)['location']['overlay_eligible'] is False


def test_calculation_refuses_successive_captures_from_same_station_relay(environment):
    client, app, source, registry = environment
    path = source / 'R/event.cfg'
    header = (source / 'S/event.cfg').read_text().splitlines()[0]
    path.write_text(header + '\n' + '\n'.join(path.read_text().splitlines()[1:]) + '\n')
    identity = client.post('/api/intake', files=payload(source) + payload(source, 'R')).json()['incident_id']
    Worker(app.state.store, registry).once()
    response = client.post(f'/api/incidents/{identity}/review', json={'revision': 1,
        'line_id': 'SYNTHETIC-DEMO', 'assignments': {
            'S/event.cfg': {'end': 'S', 'role': 'primary'},
            'R/event.cfg': {'end': 'R', 'role': 'primary'}}})
    assert response.status_code == 400
    assert 'same station and relay' in response.text
    assert app.state.store.get(identity)['state'] == 'needs_review'
    assert client.get(f'/api/incidents/{identity}').json()['result'] is None


def test_method_table_uses_section_chainage_not_linear_fraction():
    from dranalyser.faultloc.ensemble import LocationResult
    from dranalyser.faultloc.estimators import Estimate
    from dranalyser.registry.model import Line, LineSection
    from dranalyser.workbench.location_summary import summarize
    line = Line('MIXED', 'Mixed section declaration', 220, [
        LineSection(1, 0, 40, .1, .4, .3, 1.2),
        LineSection(2, 40, 100, .2, .8, .6, 2.4)], {})
    # m=.5 is 32 ohm of 64 ohm total X: 40km + 16/.8 = 60km.
    result = LocationResult(m=.5, km_from_S=60, km_from_R=40,
        interval_pu=(.49, .51), interval_km=(59.2, 60.8), method='E5', mode='two-ended', fault_type='AG',
        estimates=[Estimate('E5', .5, 0, diagnostics={'weight': 1, '_km_fn': lambda m: m * 100})])
    summary = summarize(result, line, '', {}, {})
    assert summary['km_from_S'] == 60
    assert summary['estimates'][0]['km_from_S'] == 60
    assert '_km_fn' not in summary['estimates'][0]['diagnostics']
    assert summary['interval_km'] == [59.2, 60.8]
