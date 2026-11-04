"""Standalone report interaction uses only retained frozen observations."""
from pathlib import Path
import shutil
import subprocess


def test_incident_waveform_interaction():
    node = shutil.which('node')
    assert node, 'Node is required for report readout verification.'
    subprocess.run([node, str(Path(__file__).with_name('incident_interaction.cjs'))], check=True)
