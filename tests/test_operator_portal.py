"""The four-step portal retains the source tools behind three clear tasks."""
import shutil
import subprocess
from pathlib import Path


def test_operator_portal_flow():
    node = shutil.which('node')
    assert node, 'Node is required for operator portal verification.'
    subprocess.run([node, str(Path(__file__).with_name('operator_portal.cjs'))], check=True)


def test_operator_portal_routes():
    node = shutil.which('node')
    assert node, 'Node is required for portal route verification.'
    subprocess.run([node, str(Path(__file__).with_name('operator_routes.cjs'))], check=True)


def test_primary_navigation_has_only_core_tasks():
    source = (Path(__file__).parents[1] / 'src/dranalyser/application/static/index.html').read_text()
    navigation = source.split('<nav aria-label="Main tasks">', 1)[1].split('</nav>', 1)[0]
    assert [name for name in ('upload', 'analyse', 'compare', 'report') if f'data-nav="{name}"' in navigation] == [
        'upload', 'analyse', 'compare', 'report',
    ]
    assert navigation.count('data-nav=') == 4
    assert 'catalogue' not in navigation and 'integrations' not in navigation
    assert '/static/incident-report.js' in source
