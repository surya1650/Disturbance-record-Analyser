"""Combined reports remain available without granting operational eligibility."""
import json

from dranalyser.application.worker import Worker
from tests.test_application import environment as environment
from tests.test_workbench import _write_record


def test_combined_report_has_cursor_origin_provenance_and_escaped_text(environment):
    client, app, source, registry = environment
    for name in ('one', 'two'):
        _write_record(str(source/name), 'event')
    cfg = source/'two/event.cfg'
    lines = cfg.read_text().splitlines()
    lines[-4] = '01/01/2026,00:00:00.200000'
    lines[-3] = '01/01/2026,00:00:00.300000'
    cfg.write_text('\n'.join(lines)+'\n')
    files = [('files', (f'{name}/event.{ext}', (source/name/f'event.{ext}').read_bytes()))
             for name in ('one', 'two') for ext in ('cfg', 'dat')]
    response = client.post('/api/intake', files=files, data={'name': '<script>unsafe()</script>'})
    assert response.status_code == 202
    identity = response.json()['incident_id']
    assert Worker(app.state.store, registry).once()
    before = app.state.store.get(identity)
    record = '@join:'+json.dumps(['one/event.cfg', 'two/event.cfg'])
    url = f'/api/incidents/{identity}/inspection/combined-report'
    query = dict(record=record, revision=1, cursor=250)
    response = client.get(url, params=query)
    assert response.status_code == 200, response.text
    assert '400 retained samples' in response.text
    assert 'two/event.cfg, sample 50' in response.text
    assert 'Sample RMS' in response.text and '<polyline' in response.text
    assert 'not a validated fault location' in response.text
    assert '<script>unsafe()</script>' not in response.text
    assert '&lt;script&gt;unsafe()&lt;/script&gt;' in response.text
    for cursor in (-1, 400):
        assert client.get(url, params={**query, 'cursor': cursor}).status_code == 400
    assert client.get(url, params={**query, 'record': 'one/event.cfg'}).status_code == 400
    assert app.state.store.get(identity)['files'] == before['files']
