"""The primary Report task presents the immutable canonical backend report."""
import shutil
import subprocess
from pathlib import Path


def test_incident_report_view():
    node = shutil.which('node')
    assert node, 'Node is required for incident report view verification.'
    subprocess.run([node, str(Path(__file__).with_name('incident_report_view.cjs'))], check=True)
