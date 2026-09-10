"""Real intake/worker/report revisions using the independent network oracle."""
import json

import pytest
import yaml

from dranalyser.application.worker import Worker
from tests.staged_network_oracle import upload_files
from tests import test_application as fixtures

environment = fixtures.environment


def test_network_stage_locations_require_both_reviews_and_preserve_history(environment):
    client, app, _, registry=environment
    path=registry/'demo.yaml'
    definition=yaml.safe_load(path.read_text())
    definition['sections']=[dict(from_km=0,to_km=100,r1=.09,x1=.30,r0=.24,x0=.66)]
    path.write_text(yaml.safe_dump(definition))
    assignments={f'{e}/event.cfg':dict(end=e,role='primary',protection_system='Main-1') for e in ('S','R')}
    metadata=dict(line_id='SYNTHETIC-DEMO',auto_analyse=True,assignments=assignments)
    response=client.post('/api/intake',files=upload_files(),data={'metadata':json.dumps(metadata)})
    assert response.status_code==202,response.text
    identity=response.json()['incident_id']
    worker=Worker(app.state.store,registry)
    assert worker.once()
    row=client.get(f'/api/incidents/{identity}').json()
    assert row['state']=='completed',row
    assert not row['result']['stage_locations']
    original=client.get(f'/api/incidents/{identity}/report?revision=1').content
    for rec in row['result']['relay_evidence']:
        stages=rec['stages']
        active=[s for s in stages['intervals'] if s['stable'] and s['phase_pattern']]
        assignments[rec['file']]['stage_review']=dict(
            inventory_hash=stages['inventory_hash'],reviewer='Synthetic <reviewer>',reason='Independent network schedule',
            groups={s['id']:str(i) for i,s in enumerate(active)},same_incident=True,same_circuit=True,
            stage_identity=True,location_requested=True)
    for revision, consent in [(2,True),(3,False)]:
        assert client.post(f'/api/incidents/{identity}/reanalyse?revision={revision-1}').status_code==202
        assert worker.once()
        assignments['R/event.cfg']['stage_review']['location_requested']=consent
        response=client.post(f'/api/incidents/{identity}/review',json=dict(
            revision=revision,line_id='SYNTHETIC-DEMO',assignments=assignments))
        assert response.status_code==202,response.text
        assert worker.once()
        row=client.get(f'/api/incidents/{identity}').json()
        assert row['state']=='completed',row
        result=row['result']
        assert result['location_text'].startswith('refused - Nonstationary'),result['location_text']
        assert len(result['stage_locations'])==3,result
        if consent:
            assert [s['m'] for s in result['stage_locations']]==pytest.approx([.32,.32,.73],abs=2e-5)
            report=client.get(f'/api/incidents/{identity}/report?revision={revision}').text
            assert '73.000 km' in report and 'Synthetic &lt;reviewer&gt;' in report
        else:
            assert all(s['status']=='withheld' and s['m'] is None for s in result['stage_locations'])
        assert client.get(f'/api/incidents/{identity}/report?revision=1').content==original
