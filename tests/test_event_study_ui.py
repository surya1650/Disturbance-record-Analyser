"""The event view must retain physical-end declarations and evidence limitations."""
import shutil
import subprocess
from pathlib import Path


def test_event_study_ui():
    node = shutil.which('node')
    assert node, 'Node is required for event study view verification.'
    subprocess.run([node, str(Path(__file__).with_name('event_study.cjs'))], check=True)
