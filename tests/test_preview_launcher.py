"""The preview trusts only its forwarded host and keeps its demo isolated/idempotent."""
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def launcher(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('preview_launcher', Path(__file__).parents[1] / 'start-preview.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setenv('DR_PREVIEW_PORT', '8098')
    monkeypatch.setenv('CODESPACE_NAME', 'test-space')
    monkeypatch.setenv('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', 'app.github.dev')
    return module


def test_preview_isolated_demo_exact_forwarded_host_and_restart(monkeypatch, tmp_path):
    module = launcher(monkeypatch, tmp_path)
    served = []
    monkeypatch.setattr('uvicorn.run', lambda app, **options: served.append((app, options)))
    for _ in range(2):
        module.main()
        app, options = served[-1]
        assert options == {'host': '0.0.0.0', 'port': 8098}
        assert app.state.store.root == tmp_path / 'out/web-preview/application'
        with TestClient(app, base_url='https://test-space-8098.app.github.dev') as client:
            response = client.get('/')
            assert response.status_code == 200
            assert '/static/operator-workspace.js' in response.text
            assert client.get('/', headers={'Host': 'foreign.invalid'}).status_code == 400
            rows = client.get('/api/incidents').json()['items']
            assert len(rows) == 1
            row = client.get('/api/incidents/' + rows[0]['id']).json()
            assert row['state'] == 'needs_review'
            assert len([f for f in row['bundle']['files'] if f['kind'] == 'comtrade']) == 2
    assert not (tmp_path / 'out/application').exists()


@pytest.mark.parametrize('name,value', [
    ('DR_PREVIEW_PORT', '0'), ('DR_PREVIEW_PORT', '65536'),
    ('CODESPACE_NAME', 'bad/name'),
    ('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', '*.example.com'),
    ('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', 'example.com/path'),
])
def test_invalid_preview_configuration_refused_before_creating_data(monkeypatch, tmp_path, name, value):
    module = launcher(monkeypatch, tmp_path)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        module.main()
    assert not (tmp_path / 'out').exists()
