"""Inline engineering input UI retains missing facts and immutable source/revision guards."""
from pathlib import Path
import shutil
import subprocess


def test_incident_line_inputs_ui():
    node = shutil.which('node')
    assert node, 'Node is required for inline line-input UI checks.'
    subprocess.run([node, str(Path(__file__).with_name('incident_line_inputs.cjs'))], check=True)
