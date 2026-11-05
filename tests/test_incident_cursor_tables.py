"""Offline incident cursor tables retain sample and digital evidence boundaries."""
from pathlib import Path
import shutil
import subprocess


def test_incident_cursor_tables():
    node = shutil.which('node')
    assert node, 'Node is required for report cursor table verification.'
    subprocess.run([node, str(Path(__file__).with_name('incident_cursor_tables.cjs'))], check=True)
