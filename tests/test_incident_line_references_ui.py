"""Published constants enter incident line drafts only after explicit application."""
from pathlib import Path
import shutil
import subprocess


def test_incident_line_references_ui():
    node = shutil.which('node')
    assert node, 'Node is required for published line-reference UI checks.'
    subprocess.run([node, str(Path(__file__).with_name('incident_line_references.cjs'))], check=True)
