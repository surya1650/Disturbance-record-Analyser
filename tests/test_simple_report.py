"""Verify the same plain report model used by live, print and JSON presentation."""
import shutil
import subprocess
from pathlib import Path


def test_simple_report():
    node = shutil.which('node')
    assert node, 'Node is required for simple-report verification.'
    subprocess.run([node, str(Path(__file__).with_name('simple_report.cjs'))], check=True)
